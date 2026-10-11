"""Trainable FiLM A2, exporting Gene Ko's ParametricWaveNet schema 1.

The public core contract is pinned in docs/research.md. Audio and raw physical
controls are separate: each layer modulates conv+mixin before LeakyReLU, and
the 16-tap head reads the sum of the activations. No upstream files are changed.
"""
import math
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from nam.models.parametric import ParametricNet, ParamSpec
from .architectures import A2_KERNEL_SIZES, A2_DILATIONS


def dc_block(signal, sample_rate=48000):
    """Differentiable y[n] = x[n]-x[n-1]+alpha*y[n-1], with bounded scans.

    Chunking prevents underflow of alpha**n on long captures and keeps all work
    in Torch for CPU/MPS and backprop. State crosses each chunk without detaching.
    """
    alpha = 1 - 2 * math.pi * 20 / sample_rate
    previous_x = torch.zeros_like(signal[:, :1])
    previous_y = torch.zeros_like(previous_x)
    outputs = []
    for chunk in signal.split(1024, dim=1):
        differences = chunk - torch.cat((previous_x, chunk[:, :-1]), dim=1)
        powers = torch.pow(signal.new_tensor(alpha), torch.arange(1, chunk.shape[1]+1, device=signal.device))
        filtered = powers * (torch.cumsum(differences / powers, dim=1) + previous_y)
        outputs.append(filtered)
        previous_x, previous_y = chunk[:, -1:], filtered[:, -1:]
    return torch.cat(outputs, dim=1)


class FiLMA2(ParametricNet):
    def __init__(self, params, channels, head_scale=0.01, sample_rate=48000):
        specs = tuple(ParamSpec.from_dict(p) if isinstance(p, dict) else p for p in params)
        if not 1 <= len(specs) <= 16 or any(p.type != "continuous" for p in specs):
            raise ValueError("FiLM requires 1–16 continuous controls.")
        if channels not in (3, 8) or sample_rate != 48000:
            raise ValueError("FiLM training requires 3 or 8 channels and 48000 Hz.")
        if not math.isfinite(head_scale):
            raise ValueError("FiLM head scale must be finite.")
        super().__init__(specs, sample_rate)
        self.channels = channels
        self.rechannel = nn.Conv1d(1, channels, 1, bias=False)
        self.convs = nn.ModuleList(nn.Conv1d(channels, channels, k, dilation=d)
                                   for k, d in zip(A2_KERNEL_SIZES, A2_DILATIONS))
        self.mixins = nn.ModuleList(nn.Conv1d(1, channels, 1, bias=False) for _ in A2_KERNEL_SIZES)
        self.residuals = nn.ModuleList(nn.Conv1d(channels, channels, 1) for _ in A2_KERNEL_SIZES)
        self.films = nn.ModuleList(nn.Linear(len(specs), 2*channels) for _ in A2_KERNEL_SIZES)
        self.head = nn.Conv1d(channels, 1, 16)
        self.register_buffer("head_scale", torch.tensor(float(head_scale)))
        # Start near identity modulation. Training normalizes physical ranges;
        # export folds that affine mapping into the matrices for schema 1.
        for film in self.films:
            nn.init.normal_(film.weight, std=0.005)
            with torch.no_grad():
                film.bias[:channels].fill_(1)
                film.bias[channels:].zero_()

    @property
    def pad_start_default(self):
        return False

    @property
    def receptive_field(self):
        return 1 + sum((k-1)*d for k, d in zip(A2_KERNEL_SIZES, A2_DILATIONS)) + 15

    def _encode_params(self, raw):
        raw = torch.as_tensor(raw, dtype=self._param_mins.dtype, device=self._param_mins.device)
        if raw.ndim not in (1, 2) or raw.shape[-1] != self.param_dim:
            raise ValueError("FiLM expects one control vector or one vector per audio batch.")
        if self._validate_params and (not torch.isfinite(raw).all() or
                ((raw < self._param_mins) | (raw > self._param_maxs)).any()):
            raise ValueError("FiLM controls must be finite and within their physical ranges.")
        return (raw - self._param_mins) / (self._param_maxs - self._param_mins)

    def _run_conditioned(self, x, p):
        audio = x[:, None, :]
        hidden = self.rechannel(audio)
        skip = torch.zeros_like(hidden)
        for conv, mixin, residual, film, k, d in zip(self.convs, self.mixins, self.residuals,
                                                    self.films, A2_KERNEL_SIZES, A2_DILATIONS):
            gamma, beta = film(p).reshape(-1, 2*self.channels, 1).chunk(2, dim=1)
            z = conv(F.pad(hidden, ((k-1)*d, 0))) + mixin(audio)
            activation = F.leaky_relu(gamma*z + beta, negative_slope=0.01)
            skip = skip + activation
            hidden = hidden + residual(activation)
        output = self.head(F.pad(skip, (15, 0)))[:, 0, :] * self.head_scale
        # Filter the history too, so scored outputs start with a warmed DC state.
        return dc_block(output, self.sample_rate)[:, self.receptive_field-1:]

    def _weight_tensors(self, export=False):
        yield self.rechannel.weight
        for conv, mixin, residual, film in zip(self.convs, self.mixins, self.residuals, self.films):
            yield from (conv.weight, conv.bias, mixin.weight, residual.weight, residual.bias)
            if export:
                # The player feeds raw physical values. Fold [min,max] -> [0,1]
                # into each learned affine map; no runtime/schema extension.
                weight = film.weight / (self._param_maxs - self._param_mins)
                yield weight
                yield film.bias - weight @ self._param_mins
            else:
                yield from (film.weight, film.bias)
        yield from (self.head.weight, self.head.bias, self.head_scale)

    def _export_weights(self):
        return np.concatenate([t.detach().cpu().numpy().reshape(-1) for t in self._weight_tensors(export=True)])

    def import_weights(self, weights, i=0):
        weights = np.asarray(weights, dtype=np.float32)
        if weights.ndim != 1 or not np.isfinite(weights).all():
            raise ValueError("FiLM weights must be a finite flat array.")
        tensors = list(self._weight_tensors())
        if i < 0 or len(weights)-i < sum(t.numel() for t in tensors):
            raise ValueError("Truncated FiLM weights.")
        with torch.no_grad():
            for tensor in tensors:
                end = i + tensor.numel()
                tensor.copy_(torch.as_tensor(weights[i:end].copy(), device=tensor.device).reshape(tensor.shape))
                i = end
            for film in self.films:
                film.bias.add_(film.weight @ self._param_mins)
                film.weight.mul_(self._param_maxs - self._param_mins)
        return i

    def _get_export_architecture(self):
        return "ParametricWaveNet"

    def _get_export_version(self):
        return "0.7.0"

    def _export_inner_config(self):
        return {"layers": self.channels, "head_scale": self.head_scale.item(),
                "parametric": {"type": "film", "schema_version": 1, "head_mode": "skip",
                               "condition_size": self.param_dim,
                               "film_layers": [f"layer_{i}" for i in range(23)],
                               "parameters": [{"name": p.name, "min": p.min, "max": p.max,
                                               "default": p.default} for p in self.param_specs]}}

    def _export_config(self):
        return self._export_inner_config()


def init_film(config):
    layers = config["layers"]
    if len(layers) != 1 or layers[0]["kernel_sizes"] != list(A2_KERNEL_SIZES) or layers[0]["dilations"] != list(A2_DILATIONS):
        raise ValueError("FiLM training requires the A2 topology.")
    return FiLMA2(config["params"], layers[0]["channels"], config.get("head_scale", 0.01), config.get("sample_rate", 48000))


def from_export(document):
    if (document.get("architecture"), document.get("version"), document.get("sample_rate")) != ("ParametricWaveNet", "0.7.0", 48000):
        raise ValueError("Expected a 48 kHz ParametricWaveNet 0.7.0 export.")
    config = document["config"]
    conditioning = config["parametric"]
    if conditioning.get("schema_version") != 1 or conditioning.get("head_mode") != "skip" or conditioning.get("type", "film") != "film":
        raise ValueError("Expected FiLM schema 1 with a skip head.")
    net = FiLMA2(conditioning["parameters"], config["layers"], config["head_scale"])
    if conditioning["condition_size"] != net.param_dim or net.import_weights(document["weights"]) != len(document["weights"]):
        raise ValueError("FiLM dimensions or weight count do not match.")
    return net


def export_film(model, outdir, *, output_scale=None, **kwargs):
    """Compensate the pinned trainer's joint target normalization on every export."""
    from nam.data import Dataset

    class Scale(Dataset._ScaleOutputHook):
        def apply(self, document):
            document["config"]["head_scale"] *= self.scale
            document["weights"][-1] *= self.scale
            self._adjust_metadata_loudness(document)
            return document

    original = list(model.export_model_dict_post_hooks)
    try:
        model.export_model_dict_post_hooks = [h for h in original if not isinstance(h, Dataset._ScaleOutputHook)]
        if output_scale is not None:
            if not math.isfinite(output_scale) or output_scale <= 0:
                raise ValueError("FiLM output scale must be finite and positive.")
            model.export_model_dict_post_hooks.append(Scale(scale=1/output_scale))
        model.export(outdir, **kwargs)
    finally:
        model.export_model_dict_post_hooks = original
