"""Netflix per-country weekly Top 10: breakout events and a history-only spillover baseline."""
import csv
import logging
import math
from collections import defaultdict
from datetime import date

logger = logging.getLogger(__name__)

RE_ENTRY_CUTOFF_WEEKS = 8


def load_rows(path):
    with open(path, encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    logger.info("loaded %d rows from %s", len(rows), path)
    return rows


def _week(value):
    return date.fromisoformat(value) if isinstance(value, str) else value


def title_key(row):
    return (row["show_title"], row["season_title"])


def first_entries(rows):
    """Map title_key -> {country_iso2: first week it charted there}."""
    first = defaultdict(dict)
    for row in rows:
        key, iso, week = title_key(row), row["country_iso2"], _week(row["week"])
        known = first[key].get(iso)
        if known is None or week < known:
            first[key][iso] = week
    return dict(first)


def title_categories(rows):
    categories = {}
    for row in rows:
        categories.setdefault(title_key(row), row["category"])
    return categories


def breakout_events(first, categories=None, max_origin=3, min_later=0):
    """Titles whose earliest week had 1..max_origin countries.

    `later` holds countries first charting 1..8 weeks after origin, as weeks_after_origin.
    Later joins beyond 8 weeks are re-entries or library charting and are dropped.
    """
    categories = categories or {}
    events = []
    for key in sorted(first):
        weeks = first[key]
        origin_week = min(weeks.values())
        origin_countries = sorted(c for c, w in weeks.items() if w == origin_week)
        if not 1 <= len(origin_countries) <= max_origin:
            continue
        later = {}
        for country, week in weeks.items():
            gap = (week - origin_week).days // 7
            if 1 <= gap <= RE_ENTRY_CUTOFF_WEEKS:
                later[country] = gap
        if len(later) < min_later:
            continue
        events.append({
            "title": key,
            "category": categories.get(key, ""),
            "origin_week": origin_week,
            "origin_countries": origin_countries,
            "later": later,
        })
    return events


def joined(event, country, horizon):
    return event["later"].get(country, math.inf) <= horizon


def _sigmoid(x):
    # Split by sign so exp never overflows.
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    z = math.exp(x)
    return z / (1.0 + z)


def _logit(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


class HistoryBaseline:
    """Spillover probabilities from history only.

    Let g = global join rate, and for target B:
      base_B  = (joins_B + a*g) / (trials_B + a)                    country base rate
      cat_B   = (cat_joins_B + a*base_B) / (cat_trials_B + a)       same-category rate
      pair_AB = (pair_joins_AB + k*cat_B) / (pair_trials_AB + k)    origin A seen before B
    predict(B) = mean over origin countries A of pair_AB. a=k=smoothing (defaults 5, 3).
    A trial is one (training event, non-origin country); a join is B charting within horizon.
    With extra features and a fitted blend, the output is
    sigmoid(bias + w_base*logit(pair mean) + sum_f w_f*x_f); otherwise the pure baseline.
    """

    def __init__(self, horizon=4, country_smoothing=5.0, pair_smoothing=3.0):
        self.horizon = horizon
        self.country_smoothing = country_smoothing
        self.pair_smoothing = pair_smoothing
        self.countries = []
        self.global_rate = 0.0
        self.base_rate = {}
        self.blend = None

    def fit(self, events, countries=None):
        if countries is None:
            seen = set()
            for event in events:
                seen.update(event["origin_countries"])
                seen.update(event["later"])
            countries = seen
        self.countries = sorted(countries)
        self._trials = defaultdict(int)
        self._joins = defaultdict(int)
        self._cat_trials = defaultdict(int)
        self._cat_joins = defaultdict(int)
        self._pair_trials = defaultdict(int)
        self._pair_joins = defaultdict(int)
        total_trials = total_joins = 0
        for event in events:
            origins = set(event["origin_countries"])
            for target in self.countries:
                if target in origins:
                    continue
                hit = joined(event, target, self.horizon)
                total_trials += 1
                total_joins += hit
                self._trials[target] += 1
                self._joins[target] += hit
                self._cat_trials[event["category"], target] += 1
                self._cat_joins[event["category"], target] += hit
                for origin in origins:
                    self._pair_trials[origin, target] += 1
                    self._pair_joins[origin, target] += hit
        self.global_rate = total_joins / total_trials if total_trials else 0.0
        a = self.country_smoothing
        self.base_rate = {
            c: (self._joins[c] + a * self.global_rate) / (self._trials[c] + a)
            for c in self.countries
        }
        self.blend = None
        return self

    def _history_probability(self, event, target):
        a, k = self.country_smoothing, self.pair_smoothing
        base = self.base_rate.get(target, self.global_rate)
        category = event["category"]
        cat = (self._cat_joins[category, target] + a * base) / (self._cat_trials[category, target] + a)
        pairs = [
            (self._pair_joins[o, target] + k * cat) / (self._pair_trials[o, target] + k)
            for o in event["origin_countries"]
        ]
        return sum(pairs) / len(pairs) if pairs else cat

    def predict(self, event, candidates, extra=None):
        """Return {country: probability}; `extra` is {country: {feature_name: float}}."""
        out = {}
        for country in candidates:
            p = self._history_probability(event, country)
            if extra is not None and self.blend is not None:
                p = self._blend_probability(p, extra.get(country, {}))
            out[country] = p
        return out

    def _blend_probability(self, history_p, features):
        z = self.blend["bias"] + self.blend["base_weight"] * _logit(history_p)
        for name, weight in self.blend["weights"].items():
            mean, std = self.blend["scale"][name]
            z += weight * (features.get(name, mean) - mean) / std
        return _sigmoid(z)

    def fit_blend(self, events, extras, l2=1.0, learning_rate=0.1, epochs=500):
        """Fit a logistic blend of baseline logit and extra features on training events.

        `extras` is a list parallel to `events` of {country: {feature_name: float}}.
        The history logit is in-sample here, so it is mildly optimistic; keep l2 > 0.
        """
        rows, labels = [], []
        for event, extra in zip(events, extras):
            origins = set(event["origin_countries"])
            for country in self.countries:
                if country in origins or country not in extra:
                    continue
                rows.append((_logit(self._history_probability(event, country)), extra[country]))
                labels.append(1.0 if joined(event, country, self.horizon) else 0.0)
        if not rows:
            logger.warning("no extra features supplied; blend not fitted")
            return self
        names = sorted({n for _, feats in rows for n in feats})
        scale = {}
        for name in names:
            values = [feats.get(name, 0.0) for _, feats in rows]
            mean = sum(values) / len(values)
            std = math.sqrt(sum((v - mean) ** 2 for v in values) / len(values)) or 1.0
            scale[name] = (mean, std)
        matrix = [
            [(feats.get(n, scale[n][0]) - scale[n][0]) / scale[n][1] for n in names]
            for _, feats in rows
        ]
        history = [h for h, _ in rows]
        bias, base_weight, weights = 0.0, 1.0, [0.0] * len(names)
        count = len(rows)
        for _ in range(epochs):
            grad_bias = grad_base = 0.0
            grad = [0.0] * len(names)
            for h, x, y in zip(history, matrix, labels):
                err = _sigmoid(bias + base_weight * h + sum(w * v for w, v in zip(weights, x))) - y
                grad_bias += err
                grad_base += err * h
                for i, v in enumerate(x):
                    grad[i] += err * v
            bias -= learning_rate * grad_bias / count
            # Base weight is shrunk toward 1 (the pure baseline), extras toward 0.
            base_weight -= learning_rate * (grad_base / count + l2 * (base_weight - 1.0) / count)
            weights = [w - learning_rate * (g / count + l2 * w / count) for w, g in zip(weights, grad)]
        self.blend = {
            "bias": bias,
            "base_weight": base_weight,
            "weights": dict(zip(names, weights)),
            "scale": scale,
        }
        return self


def roc_auc(scores, labels):
    """Rank-based AUC with average ranks for ties; None if one class is absent."""
    pairs = sorted(zip(scores, labels))
    positives = sum(1 for _, y in pairs if y)
    negatives = len(pairs) - positives
    if not positives or not negatives:
        return None
    rank_sum, i = 0.0, 0
    while i < len(pairs):
        j = i
        while j < len(pairs) and pairs[j][0] == pairs[i][0]:
            j += 1
        average_rank = (i + 1 + j) / 2
        rank_sum += average_rank * sum(1 for _, y in pairs[i:j] if y)
        i = j
    return (rank_sum - positives * (positives + 1) / 2) / (positives * negatives)
