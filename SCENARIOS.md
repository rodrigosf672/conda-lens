# Conda-Lens Dependency & Package Diagnostics – Full Scenario Table

## Scenario ID Prefixes
- `VC` - Version Conflict: package version requirements cannot be satisfied.
- `DUP` - Duplicate Installation: package installed multiple times (pip/conda/uv/pixi/channels).
- `MISS` - Missing Dependency: required dependency absent or wrong version.
- `PY` - Python Version Conflict: interpreter incompatible with package wheels/ABI.
- `ABI` - Platform / CUDA / Architecture Issues: compiled wheels incompatible with system.
- `G` - Dependency Graph Issues: cycles, broken edges, deep trees, orphans.
- `M` - Migration Issues: conflicts during any migration across pip ↔ conda ↔ uv ↔ pixi.
- `NC` - No Conflict: clean, valid environment (baseline expected passing cases).
- `EDGE` - Edge Cases: unusual but realistic breakages (metadata corruption, namespace overlap).
- `SOLVE` - Solver Behavior Issues: resolvers disagree, underconstrained or overconstrained environments.

## Column Meanings
- `Scenario ID`: Unique identifier for the test scenario in the Conda-Lens diagnostic suite.
- `Root Problem`: A concise description of the underlying conflict category.
- `Typical Real-World Conflict Examples`: Multi-manager examples (pip, conda, uv, pixi) based on real ecosystems.
- `Expected Detection`: What Conda-Lens should detect and classify.
- `Conflict?`: Real failure (Yes), soft warning (Soft), or no issue (No).

| Scenario ID | Root Problem | Typical Real-World Conflict Examples | Expected Detection | Conflict? |
|-------------|--------------|----------------------------------------|--------------------|-----------|
| VC-1 | Direct version mismatch | pip installs numpy 1.21 while conda pins pandas 2.2 requiring >=1.22; uv resolver selects numpy 1.23 while pixi lockfile pins numpy 1.20; scikit-image requires numpy>=1.23 but environment has older version; statsmodels breaks against too-new numpy | Version mismatch between required and installed versions | Yes |
| VC-2 | Incompatible version ranges across packages | scipy>=1.10 requires numpy>=1.20 but tensorflow<2.12 requires numpy<1.20; transformers needs tokenizers>=0.19 but pixi lock constrains <0.18; uv resolver enforces typing-extensions>=4.7 while older conda packages pin <=3.x | Conflicting dependency constraints | Yes |
| VC-3 | Hard-pinned versions impossible to reconcile | jax pins numpy==1.23.5 but conda-forge provides only 1.26; pixi lock pins protobuf>=5 but grpcio requires protobuf==4.21; jupyter-server pinned to traitlets==5.9 while extensions require <5.8 | Hard pin conflict | Yes |
| DUP-1 | Duplicate package across managers, different versions | conda numpy 1.26 + pip numpy 1.24; pixi locks pandas==2.0 but pip install brings pandas 2.2; uv installs urllib3 2.x while conda retains urllib3 1.26 | Duplicate installation with divergence | Yes |
| DUP-2 | Duplicate package across managers, same version | pandas 2.2 installed via pip and conda simultaneously; scipy duplicated across uv + pip; matplotlib present in pixi and pip editable install | Shadowing / dual-path import ambiguity | Soft |
| DUP-3 | Multiple pip distributions of same package | pip editable install + pip wheel install; local directory shadows site-packages; uv adds a local path entry while pip already installed the package | Duplicate pip metadata entries | Yes |
| DUP-4 | Duplicate across conda channels or pixi sources | defaults + conda-forge versions of pandas; pytorch-channel + conda-forge mixed install; pixi using multiple sources producing same package | Multi-source duplication | Soft |
| MISS-1 | Missing required dependency | scikit-learn missing joblib; spacy missing preshed/cymem; boto3 missing botocore; a pixi environment missing a dependency trimmed by uv | Required dependency absent | Yes |
| MISS-2 | Missing optional dependency | pandas missing pyarrow; matplotlib missing pillow; jupyter missing ipywidgets; optional runtime dependencies removed by uv | Optional dependency missing | No |
| MISS-3 | Wrong subdependency version | boto3/botocore mismatch; pip requests installs urllib3>=3 while pixi lock expects <3; jupyter-server and jupyter-client versions conflict | Required subdependency version mismatch | Yes |
| MISS-4 | Declared dependency not present (ghost dependency) | wheel references nonexistent package; renamed dependency not updated in metadata; uv stripping unused dependencies but package expects them | Invalid missing dependency | Yes |
| PY-1 | Package incompatible with installed Python version | tensorflow<2.14 does not support Python 3.12; spaCy wheels missing for Python 3.12; pixi lock references Python 3.10 while user environment is 3.12; uv resolves a package version that has no wheel for that Python | Python-version incompatibility | Yes |
| PY-2 | Python too old | pandas 2.x requires >=3.8; numpy modern wheels require >=3.9; uv and pixi resolvers refuse installing packages on Python 3.7 | Python too old for dependencies | Yes |
| PY-3 | Compatible Python environment | Python 3.10 with numpy/pandas/scipy; Python 3.11 with ML stack; uv and pixi resolve consistent wheels | No issues detected | No |
| PY-4 | Forward ABI incompatibility | wheels built only for <=3.11 installed into 3.12; binary extension ABI mismatch across uv or pixi; conda-forge build not available for user’s interpreter | Wheel/ABI mismatch | Yes |
| ABI-1 | CUDA build installed on CPU-only system | torch+cu118 installed while no GPU present; tensorflow-gpu installed on pixi environment lacking GPU support; jaxlib-cuda installed via pip inside conda CPU env | CUDA/CPU mismatch | Soft |
| ABI-2 | CUDA toolkit mismatch | cudatoolkit 11.2 + pycuda built for 11.8; torch build expecting CUDA 12.1 but system nvcc is 11.8; pixi selects mismatched CUDA build; uv installs incompatible wheel | Toolkit/driver mismatch | Yes |
| ABI-3 | Wrong architecture wheel | x86_64 wheel installed on ARM macOS; linux_x86 wheel installed on aarch64; uv resolves linux wheels on macOS; pip installs Windows build inside WSL | Architecture mismatch | Yes |
| ABI-4 | GPU driver incompatibility | NVIDIA driver too old; incompatible CUDA minor version; mismatched container image vs host driver; pixi environment pinned to unsupported CUDA version | GPU driver conflict | Yes |
| G-1 | Cyclic dependency | A→B→C→A loops; uv editable installs causing circular references; pixi lock incorrectly flattened creating a cycle | Detect cycle | Yes |
| G-2 | Orphan package | six unused; tomli leftover after Python 3.11 upgrade; obsolete dependency from conda removed but pip still imports it | Identify unused package | No |
| G-3 | Deep dependency chain | transformers deep tree; uv flattening shows 20–40 transitive deps; pixi lockfile reproducing long subdeps | Graph is valid; no conflict | No |
| G-4 | Broken dependency edges | missing REQUIRES.txt; incomplete METADATA; dependency renamed but pip/conda/pixi metadata unsynced | Broken dependency graph | Yes |
| M-1 | Package unavailable in target manager | pip-only package missing on conda; uv resolver finds version but pixi registry lacks it; conda-forge version missing in defaults | Migration impossible | Yes |
| M-2 | Migration feasible | DS stack fully resolvable in pip or conda; uv reproduces environment exactly; pixi lockfile matches all dependencies | Migration valid | No |
| M-3 | PEP 508 markers break migration | sys_platform markers differ across pip and conda; python_version conditions; uv strict evaluation vs pip's permissive resolution; pixi fails when markers mismatch lockfile | Marker logic conflict | Yes |
| M-4 | Channel/source mismatch | package exists only in conda-forge; pinned build not in pixi registries; uv resolves version unavailable in pip | Resolver failure | Yes |
| NC-1 | Clean DS stack | compatible numpy/pandas/scipy; same versions across pip/conda/uv/pixi | No conflict | No |
| NC-2 | Minimal pip-only ML environment | numpy + pandas + matplotlib fully compatible; uv reproduces reliably | No conflict | No |
| NC-3 | All packages from conda-forge or pixi registry | consistent builds, no multi-channel or multi-source conflict | No conflict | No |
| NC-4 | Very small environment | few pinned packages; pip/conda/uv/pixi consistent | No conflict | No |
| EDGE-1 | Editable install shadowing installed package | pip install -e + pip install; uv adds path override; local folder overrides conda env; pixi overlay directory masking installed wheel | Shadowing detected | Yes |
| EDGE-2 | Corrupted metadata | missing METADATA, missing REQUIRES, broken wheel; pixi lock referencing corrupt artifact; uv installing incomplete wheel | Metadata corruption error | Yes |
| EDGE-3 | Namespace overlaps | google.* split across google-auth, protobuf, google-api-core; azure.* split across multiple azure-* packages; uv resolving conflicting namespace contributors | Overlap OK unless versions conflict | Soft |
| EDGE-4 | Wheel missing metadata files | missing REQUIRES.txt; incorrect MANIFEST.in; wheel built incorrectly; pixi resolves incomplete wheel | Missing metadata | Yes |
| EDGE-5 | Nonexistent dependency (ghost) | upstream typo; dependency removed but still declared; uv resolves stripped dependency incorrectly; pixi lock out-of-sync with published metadata | Missing/invalid dependency | Yes |
| SOLVE-1 | Unconstrained versions lead to nondeterminism | pip installs newest numpy breaking older stack; uv installing latest versions causing mismatches; pixi lock unspecified, leading to drift | Underdetermined environment | Soft |
| SOLVE-2 | Over-constrained environment | fully pinned environment conflicting across pip/conda; pixi strict lock blocking resolution; uv unable to reconcile pins | Over-constrained solver | Soft |
| SOLVE-3 | Multi-manager priority conflict | pip overrides conda-installed libs; uv and pip disagree on resolver choices; pixi lock incompatible with pip-installed overrides | Manager precedence conflict | Yes |
| SOLVE-4 | Subdependency conflict | urllib3 vs requests mismatches; idna vs charset-normalizer conflicts; pixi reproduces incompatible tree; uv generates incompatible versions | Subdependency-level conflict | Yes |
