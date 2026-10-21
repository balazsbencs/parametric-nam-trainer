"""Package only source and instructions for transfer to a Mac."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
out = root / 'dist' / 'parametric-mac.zip'
out.parent.mkdir(exist_ok=True)
files = [root / name for name in ('README.md', 'pyproject.toml', '.python-version', '.gitignore',
          'Install.command', 'Capture.command', 'Train.command', 'PRODUCT.md', 'DESIGN.md', 'CHANGELOG.md')]
for folder in ('parametric_mac', 'docs', 'tests', 'scripts', 'cloud'):
    files.extend(p for p in (root / folder).rglob('*') if p.is_file() and
                 '__pycache__' not in p.parts and p.suffix != '.pyc')
# Carry the native design record and evidence referenced by the shipped docs.
for name in ('.impeccable/design.json', '.impeccable/config.json'):
    path = root / name
    if path.is_file():
        files.append(path)
evidence = root / '.impeccable/review/native'
if evidence.is_dir():
    files.extend(p for p in evidence.iterdir() if p.is_file())
with ZipFile(out, 'w', ZIP_DEFLATED) as archive:
    for path in sorted(files):
        archive.write(path, Path('parametric-mac') / path.relative_to(root))
print(out)
print(f'{len(files)} source/documentation files; environments, upstream checkout and audio excluded.')
