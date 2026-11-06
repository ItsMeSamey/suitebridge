# Third-party notices and corpus provenance

SuiteBridge's own source is covered by its top-level LICENSE. The third-party corpus below retains its own license. Python interpreters, virtual environments and dependency wheels are not included in this release.

## Redistributed corpus: Python-Markdown 3.9

This release includes one unchanged upstream source distribution, `markdown-3.9.tar.gz` (364,585 bytes), acquired from the primary PyPI release on 2026-11-06. Its observed SHA-256 matched the digest in the retained PyPI metadata:

`d2900fe1782bd33bdbbd56859defef70c2e78fc46668f8eb9df3128138f2cb6a`

- [Version metadata](https://pypi.org/pypi/Markdown/3.9/json)
- [Original source archive](https://files.pythonhosted.org/packages/8d/37/02347f6d6d8279247a5837082ebc26fc0d5aaeaf75aa013fcbb433c777ab/markdown-3.9.tar.gz)
- License: BSD-3-Clause. The archive's `markdown-3.9/LICENSE.md` has SHA-256 `7ba4eb6d10b32b2d11dce13821340351cdbbb30ba8ccc67841db2ffd86e79aca`.

The original copyright notices, license, test headers and fixture contents remain in the archive. Extract it intact when reproducing the corpus checks. Any deliberate regression variants are applied to separate copies and do not replace the original archive.

The measured scope is **all tests discoverable in the pinned Python-Markdown 3.9 PyPI source distribution, in the documented target environment**. This is not the full upstream repository test suite. Upstream `MANIFEST.in` includes only `*.txt`, `*.html` and `*.py` under `tests`. The legacy TestPhp, TestPl2004 and TestPl2007 classes need `*.text` inputs; TestPhp also expects `*.xhtml` outputs. The source distribution omits `tests/php` and contains legacy `tests/pl` HTML outputs without their matching `.text` inputs. Those three classes consequently generate no cases. This omission predates SuiteBridge and was not introduced to select favorable tests.

The tested target environment has no Pygments. It discovers 1,024 native cases with five skips. A separate retained experiment using Pygments 2.21.0 in the target environment produced 20 failures and one error; that configuration is not claimed to reproduce the passing corpus result. Pygments belongs in the separate pytest frontend environment used for these checks.

One unchanged compressed Markdown source archive is the complete third-party corpus payload. Other investigated projects, competitor tools, downloaded package wheels and development virtual environments are not redistributed.

## Dependencies used for validation, not bundled

The recorded validation used Python 3.14.8. The frontend used pytest 9.2.0 and its following dependency versions. Each artifact hash below identifies the unchanged wheel retained from primary PyPI acquisition; it is a wheel hash, not a source-archive hash. Installation requirements may be fulfilled separately using the package installer. Bundling these wheels is unnecessary to redistribute the SuiteBridge source and corpus.

| Package | Version | License | Retained wheel SHA-256 |
| --- | --- | --- | --- |
| pytest | 9.2.0 | MIT | `07acdcf88ec174f907dc01af70bf52d49b014bbab03faeeade31c96b18c2e588` |
| iniconfig | 2.3.1 | MIT | `9121e2c1fdb355232495be3194c8dfe87ccc2d5dee45947b78e68f499790d7a7` |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | `d7193f7c8e4e93f444fde0262bf90af30e16fa0ad0ad44cb553c87339b23cd1c` |
| pluggy | 1.7.0 | MIT | `7dd7b0d8832ba3cb632c306926ded123429211b83641b35dc5c41ad2d34f9bec` |
| Pygments | 2.21.0 | BSD-2-Clause | `2363c69b61c4a97c838da3b130dcd6468f4848992b21a82f2a63ec34377137d9` |

Version metadata: [pytest](https://pypi.org/pypi/pytest/9.2.0/json), [iniconfig](https://pypi.org/pypi/iniconfig/2.3.1/json), [packaging](https://pypi.org/pypi/packaging/26.3/json), [pluggy](https://pypi.org/pypi/pluggy/1.7.0/json), [Pygments](https://pypi.org/pypi/Pygments/2.21.0/json).

Licenses were checked against the retained wheel contents, not inferred from a missing legacy metadata field. Their license-file SHA-256 values are:

| Package | File within its distribution metadata | SHA-256 |
| --- | --- | --- |
| pytest | `licenses/LICENSE` | `ca836a5f9ecca3b2f350230faa20a48fb8b145653b5568d784862df864706b9b` |
| iniconfig | `licenses/LICENSE` | `3409fa91f7ace557894632676656e32264fe5ef7581535725dc9a23774551bd4` |
| packaging | `licenses/LICENSE` | `cad1ef5bd340d73e074ba614d26f7deaca5c7940c3d8c34852e65c4909686c48` |
| packaging | `licenses/LICENSE.APACHE` | `0d542e0c8804e39aa7f37eb00da5a762149dc682d7829451287e11b938e94594` |
| packaging | `licenses/LICENSE.BSD` | `b70e7e9b742f1cc6f948b34c16aa39ffece94196364bc88ff0d2180f0028fac5` |
| pluggy | `licenses/LICENSE` | `d6b65e6c213a5d0b577911d34d6e5949b9f59d76c238c5071a2f3fc16cfb2606` |
| Pygments | `licenses/LICENSE` | `a9d66f1d526df02e29dce73436d34e56e8632f46c275bbdffc70569e882f9f17` |

The native Markdown target used packaging 26.3 and PyYAML 6.0.3 without pytest or Pygments. PyYAML is MIT-licensed, copyright 2017-2021 Ingy dot Net and 2006-2016 Kirill Simonov. The tested PyYAML files were copied from an already installed package into the isolated target environment. No PyYAML source archive or wheel was acquired for this validation, so no download hash is claimed.

Retained PyYAML provenance identifies `yaml/__init__.py` by SHA-256 `b19dfcc333d6a75dfd73073901164507252f271b41d3b5f7d85510033a0547a7`, metadata by `03c3b415ed38d09faedc49360e930769b40c58f68585e6de00e2e4916a858d34`, and its complete MIT license by `8d3928f9dc4490fd635707cb88eb26bd764102a7282954307d3e5167a577e8a4`. These identify retained installed files and do not imply a portable binary distribution. PyYAML and Python must be provided separately for corpus reproduction.

## Python-Markdown license

The following text reproduces the archive's license; the original file and individual source notices remain authoritative.

BSD 3-Clause License

Copyright 2007, 2008 The Python Markdown Project (v. 1.7 and later)  
Copyright 2004, 2005, 2006 Yuri Takhteyev (v. 0.2-1.6b)  
Copyright 2004 Manfred Stienstra (the original version)

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
