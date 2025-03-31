# Multilingual ROUGE Scoring

This is a port of [XL-Sum](https://github.com/csebuetnlp/xl-sum) repository as a simple utility to utilize the multilingual RougeL utility for [MIRAGE-Bench](https://github.com/vectara/mirage-bench). 

**I do not own the codebase so any questions must be redirected to [XL-Sum](https://github.com/csebuetnlp/xl-sum).**

## Installation

To install this library, please use the following:

```bash
python -m unidic download # for japanese segmentation
pip install -U multilingual-rouge
```
Alternatively to install from source:

```bash
python -m unidic download # for japanese segmentation
pip install -e .
```

## Overview

ROUGE is the de facto evaluation metric used for text summarization. However, it was designed specifically for evaluating English texts. Due to the nature of the metric, scores are heavily dependent on text tokenization / stemming / unnecessary character removal, etc. This repo tries to address these issues by adding the following main features using an adaptation of [rouge-score: Google's rouge implementation](https://github.com/google-research/google-research/tree/master/rouge).

* Enables multilingual ROUGE scoring by making use of popular word segmentation / stemming algorithms for various languages.
* Removes only punctuation characters according to unicode data tables as part of text normalization. This enables basic rouge scoring even with the absence of a segmenter / stemmer for any language.
* Provides an easy to use interface for using custom tokenization / stemming implementations.
  
### Supported language names for stemming
`bengali`, `hindi`, `turkish`, `arabic`, `danish`, `dutch`, `english`, `finnish`, `french`, `german`, `hungarian`, `italian`, `norwegian`, `portuguese`, `romanian`, `russian`, `spanish`, `swedish`

### Supported language names for word segmentation
`chinese`, `thai`, `japanese`, `burmese`

## Setup
```bash
pip3 install -r requirements.txt
python3 -m unidic download # for japanese segmentation
pip3 install --upgrade ./
```

## Example Usage

### Using CLI
```bash
python -m rouge_score.rouge \
    --target_filepattern=*.targets \
    --prediction_filepattern=*.decodes \
    --output_filename=scores.csv \
    --use_stemmer=true \ # optional
    --lang="bengali" # optional
```


### Using python

* **Default usage**


```python
from multilingual_rouge import rouge_scorer

scorer = rouge_scorer.RougeScorer(['rouge1', 'rougeL'], use_stemmer=True)
scores = scorer.score('The quick brown fox jumps over the lazy dog',
                      'The quick brown dog jumps on the log.')
```
* **With provided language**
  
```python
from multilingual_rouge import rouge_scorer

scorer = rouge_scorer.RougeScorer(['rouge1', 'rougeL'], use_stemmer=True, lang="bengali")
scores = scorer.score('তোমার সাথে দেখা হয়ে ভালো লাগলো।',
                      'আপনার সাথে দেখা হয়ে ভালো লাগলো।')
```

* **With your own stemming / word segmentation implementation**
  
    Custom `stemmer`/ `tokenizer` implementations must be `callable` objects, i.e. functions or classes with `__call__` method implemented. If `lang` is also given, user provided implementations take precedence over the library provided ones.

```python
from multilingual_rouge import rouge_scorer

# example with custom stemming
class DummyStemmer(object):
    def __call__(self, token):
        stem = ""
        # your stemmer implementation
        return stem

# example with custom segmenter/tokenizer
def dummy_tokenize(text):
    tokens = []
    # your tokenizer implementation
    return tokens

scorer = rouge_scorer.RougeScorer(['rouge1', 'rougeL'], use_stemmer=True, 
                                    callable_stemmer=DummyStemmer(),
                                    callable_tokenizer=dummy_tokenize)
scores = scorer.score('The quick brown fox jumps over the lazy dog',
                      'The quick brown dog jumps on the log.')
                      
```

* To see list of all available keyword arguments and reference stemmer and segmenter implementations refer to [rouge_scorer.py](multilingual_rouge/rouge_scorer.py), [stemmers.py](multilingual_rouge/stemmers.py) and [tokenizers.py](multilingual_rouge/tokenizers.py) 


## License

Originally licensed under the
[Apache 2.0](https://github.com/google-research/google-research/blob/master/LICENSE)
License.