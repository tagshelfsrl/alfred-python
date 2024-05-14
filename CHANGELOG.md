# Changelog

## 0.1.0 (2024-05-14)


### Features

* add job domain ([#9](https://github.com/tagshelfsrl/alfred-python/issues/9)) ([aa9528c](https://github.com/tagshelfsrl/alfred-python/commit/aa9528c18d35c2789fcda0590a7f270a691bc8f5))
* Add LICENSE and pyproject.toml configuration ([#1](https://github.com/tagshelfsrl/alfred-python/issues/1)) ([e674ba6](https://github.com/tagshelfsrl/alfred-python/commit/e674ba62777ea05fb5b0ebf4ed91c578dd3a02fa))
* **AL-860:** Implement base HTTP client class ([#3](https://github.com/tagshelfsrl/alfred-python/issues/3)) ([da0d92e](https://github.com/tagshelfsrl/alfred-python/commit/da0d92e19b7279f18eec918195f5ca76bc1f09c7))
* **AL-866:** Implement authentication methods supported in Alfred ([#4](https://github.com/tagshelfsrl/alfred-python/issues/4)) ([25c1530](https://github.com/tagshelfsrl/alfred-python/commit/25c153060129b73ef8a0511c28b98c5471905dee))
* **AL-867:** Implement OAuth refresh token handler  ([#5](https://github.com/tagshelfsrl/alfred-python/issues/5)) ([adc29d5](https://github.com/tagshelfsrl/alfred-python/commit/adc29d5562bf74dec97b3428e4dcb8bebfd201f5))
* **AL-869:** Implemented Data Points domain ([#6](https://github.com/tagshelfsrl/alfred-python/issues/6)) ([faf0d09](https://github.com/tagshelfsrl/alfred-python/commit/faf0d09995d7a2ad563f7145c4e7c4b7395d367a))
* **AL-870:** implement session domain ([#7](https://github.com/tagshelfsrl/alfred-python/issues/7)) ([823afa0](https://github.com/tagshelfsrl/alfred-python/commit/823afa0b415411cd4a0a824291ca3565676f54cf))
* **AL-871:** Implement Files domain class and methods ([#14](https://github.com/tagshelfsrl/alfred-python/issues/14)) ([f34469d](https://github.com/tagshelfsrl/alfred-python/commit/f34469d8a0647691fc139da35bcc0376e3785651))
* AL-886 enables pypi publishes ([#20](https://github.com/tagshelfsrl/alfred-python/issues/20)) ([85abecb](https://github.com/tagshelfsrl/alfred-python/commit/85abecb051e6304ccbf92f47ebc6834572df5880))
* introduce response parsing based on configurable option at instance and endpoint level. ([#11](https://github.com/tagshelfsrl/alfred-python/issues/11)) ([cc0995d](https://github.com/tagshelfsrl/alfred-python/commit/cc0995d9e66c5ed4dc84761a1212d1c6d0ae6119))
* setup functionality to apply throttling when the remaining requests get to a certain threshold. ([#15](https://github.com/tagshelfsrl/alfred-python/issues/15)) ([bceb818](https://github.com/tagshelfsrl/alfred-python/commit/bceb818570094daf258eb15ca5592047ec9f2808))
* Update README documentation ([#12](https://github.com/tagshelfsrl/alfred-python/issues/12)) ([4724ddb](https://github.com/tagshelfsrl/alfred-python/commit/4724ddb82111be4f7ffa8ee08767cd81306a57b0))


### Bug Fixes

* **AL-869:** Set overrides as empty dict if value is None ([#8](https://github.com/tagshelfsrl/alfred-python/issues/8)) ([c446c89](https://github.com/tagshelfsrl/alfred-python/commit/c446c89ef0ca5f2152e1041ec5a007b7f89eae9e))
* Fixed bad imports ([#17](https://github.com/tagshelfsrl/alfred-python/issues/17)) ([ac4afbd](https://github.com/tagshelfsrl/alfred-python/commit/ac4afbdce6f0ded162d5fe5196a5d5804de9cc91))
* Updated domain methods to expect a tuple instead of a Response object ([#16](https://github.com/tagshelfsrl/alfred-python/issues/16)) ([6f28402](https://github.com/tagshelfsrl/alfred-python/commit/6f284020611c99fc4b2482b25fc51fe783cf37ac))
* Use response headers to get the content-type instead of request ([#13](https://github.com/tagshelfsrl/alfred-python/issues/13)) ([e54eeab](https://github.com/tagshelfsrl/alfred-python/commit/e54eeab7bc32736210106b65b4c766cf9fe5133f))