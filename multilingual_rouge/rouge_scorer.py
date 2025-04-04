# Copyright 2020 The Google Research Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Lint as: python2, python3
"""Computes rouge scores between two text blobs.

Implementation replicates the functionality in the original ROUGE package.
Modifications were made to tokenization and stemming schemes to accomodate
rouge calculation for various languages.

"""

from __future__ import annotations

import collections
import re
import warnings

import pyonmttok
import six

from multilingual_rouge import scoring
from multilingual_rouge import tokenization_wrapper as tokenize
from multilingual_rouge.stemmers import LANG2STEMMER
from multilingual_rouge.tokenizers import (
    LANG2TOKENIZER,
    BasicTokenizer,
    whitespace_tokenize,
)

# Alternate names for predefined languages
SPECIAL_LANGID_CONVERSION_MAP = {
    "bengali": ["bangla"],
    "turkish": ["turkce"],
    "chinese": ["chinese_simplified", "chinese_traditional"],
    "spanish": ["mundo"],
}
SPECIAL_LANGID_CONVERSION_MAP = {lang: k for k, v in SPECIAL_LANGID_CONVERSION_MAP.items() for lang in v}


class MultiTokenizer:
    """Tokenizes/segments texts for various languages"""

    def __init__(self, lang=None, callable_tokenizer=None):
        self.pretokenizer = pyonmttok.Tokenizer("aggressive")
        self.sanitizer = BasicTokenizer()
        self.lang = lang
        self.tokenizer = None
        if callable_tokenizer:
            self.tokenizer = callable_tokenizer
        elif lang:
            tokenizer_obj = LANG2TOKENIZER.get(lang, None)
            self.tokenizer = tokenizer_obj() if tokenizer_obj else None

    def __call__(self, text):
        tokens = []
        # cleans text and removes punctuations
        text = " ".join(self.sanitizer(text.strip()))

        if self.tokenizer:
            tokens = self.tokenizer(text)

        if not tokens and text:
            if self.tokenizer:
                warnings.warn(
                    "-" * 5 + "No tokens found using inferred tokenizer," + " switching to default tokenizer" + "-" * 5
                )
            # better numeric tokenization for non cjk langs
            text = " ".join(self.pretokenizer.tokenize(text)[0])
            tokens = whitespace_tokenize(self.sanitizer.tokenize_chinese_chars(text))

        return tokens


class MultiStemmer:
    """Wrapper for stemmers in multiple languages"""

    def __init__(self, lang=None, callable_stemmer=None, min_char_length=3):
        """Initializes a new Stemmer.

        Args:
                lang: Language to be used for stemming.
                callable_stemmer: Optional user defined callable object
                        to be used for stemming.
                min_char_length: Minimum required character length of a token
                        for it to be stemmed.
        """
        # default stemmer to make things compatible
        # with the original implementation
        self.stemmer = LANG2STEMMER.get("porter")()
        self.min_char_length = min_char_length
        if callable_stemmer:
            self.stemmer = callable_stemmer
        elif lang:
            stemmer_obj = LANG2STEMMER.get(lang, None)
            if not stemmer_obj:
                self.stemmer = None
                warnings.warn("-" * 5 + f"unknown stemmer language-> {lang}" + "-" * 5)
            else:
                self.stemmer = stemmer_obj()

    def __call__(self, token):
        stem = token
        if self.stemmer and len(token) > self.min_char_length:
            stem = self.stemmer(token)

        return stem


class RougeScorer(scoring.BaseScorer):
    """Calculate rouges scores between two blobs of text.

    Sample usage:
            scorer = RougeScorer(['rouge1', 'rougeL'], use_stemmer=True, lang="english")
            scores = scorer.score('The quick brown fox jumps over the lazy dog',
                                                                                                    'The quick brown dog jumps on the log.')
    """

    def __init__(self, rouge_types, **kwargs):
        """Initializes a new RougeScorer.

        Valid rouge types that can be computed are:
                rougen (e.g. rouge1, rouge2): n-gram based scoring.
                rougeL: Longest common subsequence based scoring.

        Args:
                rouge_types: A list of rouge types to calculate.
                **kwargs: optional keyword arguments

        Keyword Arguments:
                use_stemmer: Bool indicating whether a stemmer should be used to
                        strip word suffixes to improve matching.
                callable_tokenizer: A callable object that returns a list of tokens
                        given a piece of text
                callable_stemmer: A callable object that returns the stem of a token
                        given a text token
                min_char_length: Minimum char length of a token to trigger stemming.
                        Defaults to 3.

        Returns:
                A dict mapping rouge types to Score tuples.
        """
        lang = kwargs.get("lang", None)
        if lang and lang in SPECIAL_LANGID_CONVERSION_MAP:
            # replace lang with one of supported codes
            lang = SPECIAL_LANGID_CONVERSION_MAP[lang]

        use_stemmer = kwargs.get("use_stemmer", False)
        callable_stemmer = kwargs.get("callable_stemmer", None)
        callable_tokenizer = kwargs.get("callable_tokenizer", None)
        min_char_length = kwargs.get("min_char_length", 3)

        self.rouge_types = rouge_types
        self._tokenizer = MultiTokenizer(lang, callable_tokenizer)
        self._stemmer = MultiStemmer(lang, callable_stemmer, min_char_length) if use_stemmer else None

    def score(self, target, prediction):
        """Calculates rouge scores between the target and prediction.

        Args:
                target: Text containing the target (ground truth) text.
                prediction: Text containing the predicted text.
        Returns:
                A dict mapping each rouge type to a Score object.
        Raises:
                ValueError: If an invalid rouge type is encountered.
        """

        target_tokens = tokenize.tokenize(target, self._stemmer, self._tokenizer)
        prediction_tokens = tokenize.tokenize(prediction, self._stemmer, self._tokenizer)
        result = {}

        for rouge_type in self.rouge_types:
            if rouge_type == "rougeL":
                # Rouge from longest common subsequences.
                scores = _score_lcs(target_tokens, prediction_tokens)
            elif rouge_type == "rougeLsum":
                # Note: Does not support multi-line text.
                def get_sents(text):
                    # Assume sentences are separated by newline.
                    sents = six.ensure_str(text).split("\n")
                    sents = [x for x in sents if len(x)]
                    return sents

                target_tokens_list = [tokenize.tokenize(s, self._stemmer) for s in get_sents(target)]
                prediction_tokens_list = [tokenize.tokenize(s, self._stemmer) for s in get_sents(prediction)]
                scores = _summary_level_lcs(target_tokens_list, prediction_tokens_list)
            elif re.match(r"rouge[0-9]$", six.ensure_str(rouge_type)):
                # Rouge from n-grams.
                n = int(rouge_type[5:])
                if n <= 0:
                    raise ValueError("rougen requires positive n: %s" % rouge_type)
                target_ngrams = _create_ngrams(target_tokens, n)
                prediction_ngrams = _create_ngrams(prediction_tokens, n)
                scores = _score_ngrams(target_ngrams, prediction_ngrams)
            else:
                raise ValueError("Invalid rouge type: %s" % rouge_type)
            result[rouge_type] = scores

        return result


def _create_ngrams(tokens, n):
    """Creates ngrams from the given list of tokens.

    Args:
            tokens: A list of tokens from which ngrams are created.
            n: Number of tokens to use, e.g. 2 for bigrams.
    Returns:
            A dictionary mapping each bigram to the number of occurrences.
    """

    ngrams = collections.Counter()
    for ngram in (tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)):
        ngrams[ngram] += 1
    return ngrams


def _score_lcs(target_tokens, prediction_tokens):
    """Computes LCS (Longest Common Subsequence) rouge scores.

    Args:
            target_tokens: Tokens from the target text.
            prediction_tokens: Tokens from the predicted text.
    Returns:
            A Score object containing computed scores.
    """

    if not target_tokens or not prediction_tokens:
        return scoring.Score(precision=0, recall=0, fmeasure=0)

    # Compute length of LCS from the bottom up in a table (DP appproach).
    lcs_table = _lcs_table(target_tokens, prediction_tokens)
    lcs_length = lcs_table[-1][-1]

    precision = lcs_length / len(prediction_tokens)
    recall = lcs_length / len(target_tokens)
    fmeasure = scoring.fmeasure(precision, recall)

    return scoring.Score(precision=precision, recall=recall, fmeasure=fmeasure)


def _lcs_table(ref, can):
    """Create 2-d LCS score table."""
    rows = len(ref)
    cols = len(can)
    lcs_table = [[0] * (cols + 1) for _ in range(rows + 1)]
    for i in range(1, rows + 1):
        for j in range(1, cols + 1):
            if ref[i - 1] == can[j - 1]:
                lcs_table[i][j] = lcs_table[i - 1][j - 1] + 1
            else:
                lcs_table[i][j] = max(lcs_table[i - 1][j], lcs_table[i][j - 1])
    return lcs_table


def _backtrack_norec(t, ref, can):
    """Read out LCS."""
    i = len(ref)
    j = len(can)
    lcs = []
    while i > 0 and j > 0:
        if ref[i - 1] == can[j - 1]:
            lcs.insert(0, i - 1)
            i -= 1
            j -= 1
        elif t[i][j - 1] > t[i - 1][j]:
            j -= 1
        else:
            i -= 1
    return lcs


def _summary_level_lcs(ref_sent, can_sent):
    """ROUGE: Summary-level LCS, section 3.2 in ROUGE paper.

    Args:
            ref_sent: list of tokenized reference sentences
            can_sent: list of tokenized candidate sentences

    Returns:
            summary level ROUGE score
    """
    if not ref_sent or not can_sent:
        return scoring.Score(precision=0, recall=0, fmeasure=0)

    m = sum(map(len, ref_sent))
    n = sum(map(len, can_sent))
    if not n or not m:
        return scoring.Score(precision=0, recall=0, fmeasure=0)

    # get token counts to prevent double counting
    token_cnts_r = collections.Counter()
    token_cnts_c = collections.Counter()
    for s in ref_sent:
        # s is a list of tokens
        token_cnts_r.update(s)
    for s in can_sent:
        token_cnts_c.update(s)

    hits = 0
    for r in ref_sent:
        lcs = _union_lcs(r, can_sent)
        # Prevent double-counting:
        # The paper describes just computing hits += len(_union_lcs()),
        # but the implementation prevents double counting. We also
        # implement this as in version 1.5.5.
        for t in lcs:
            if token_cnts_c[t] > 0 and token_cnts_r[t] > 0:
                hits += 1
                token_cnts_c[t] -= 1
                token_cnts_r[t] -= 1

    recall = hits / m
    precision = hits / n
    fmeasure = scoring.fmeasure(precision, recall)
    return scoring.Score(precision=precision, recall=recall, fmeasure=fmeasure)


def _union_lcs(ref, c_list):
    """Find union LCS between a ref sentence and list of candidate sentences.

    Args:
            ref: list of tokens
            c_list: list of list of indices for LCS into reference summary

    Returns:
            List of tokens in ref representing union LCS.
    """
    lcs_list = [lcs_ind(ref, c) for c in c_list]
    return [ref[i] for i in _find_union(lcs_list)]


def _find_union(lcs_list):
    """Finds union LCS given a list of LCS."""
    return sorted(list(set().union(*lcs_list)))


def lcs_ind(ref, can):
    """Returns one of the longest lcs."""
    t = _lcs_table(ref, can)
    return _backtrack_norec(t, ref, can)


def _score_ngrams(target_ngrams, prediction_ngrams):
    """Compute n-gram based rouge scores.

    Args:
            target_ngrams: A Counter object mapping each ngram to number of
                    occurrences for the target text.
            prediction_ngrams: A Counter object mapping each ngram to number of
                    occurrences for the prediction text.
    Returns:
            A Score object containing computed scores.
    """

    intersection_ngrams_count = 0
    for ngram in six.iterkeys(target_ngrams):
        intersection_ngrams_count += min(target_ngrams[ngram], prediction_ngrams[ngram])
    target_ngrams_count = sum(target_ngrams.values())
    prediction_ngrams_count = sum(prediction_ngrams.values())

    precision = intersection_ngrams_count / max(prediction_ngrams_count, 1)
    recall = intersection_ngrams_count / max(target_ngrams_count, 1)
    fmeasure = scoring.fmeasure(precision, recall)

    return scoring.Score(precision=precision, recall=recall, fmeasure=fmeasure)
