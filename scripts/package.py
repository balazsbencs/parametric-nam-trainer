"""Package only source and instructions for transfer to a Mac."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
out = root / 'dist' / 'parametric-mac.zip'
out.parent.mkdir(exist_ok=True)
files = [root / name for name in ('README.md', 'pyproject.toml', '.gitignore',
          'Install.command', 'Capture.command', 'Train.command', 'PRODUCT.md', 'DESIGN.md')]
for folder in ('parametric_mac', 'docs', 'tests', 'scripts'):
    files.extend(p for p in (root / folder).rglob('*') if p.is_file() and
                 '__pycache__' not in p.parts and p.suffix != '.pyc')
with ZipFile(out, 'w', ZIP_DEFLATED) as archive:
    for path in sorted(files):
        archive.write(path, Path('parametric-mac') / path.relative_to(root))
print(out)
print(f'{len(files)} source/documentation files; environments, upstream checkout and audio excluded.')
