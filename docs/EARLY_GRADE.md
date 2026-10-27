# Early grade: top picks

Registered before the Netflix week of 25 Oct is published. The commit timestamp of this file is the registration.

## Definition

Top-pick early grade. For every breakout locked in the ledger, take its single highest-probability forecast country (ties: the first in the ledger order). After each new Netflix week, count how many of those top picks have already charted the title (joined after the origin week and within the 4-week horizon), out of all locked breakouts whose origin week is before the latest Netflix week.

Compare with the expected count if the forecasts were exactly calibrated: the sum of those top-pick probabilities.

Also report the same for a naive baseline that picks, for each breakout, the country that charts the most titles overall (the most frequent Top 10 country in the training history), with its own observed count.

Reported every week whichever way it goes. The 4-week result on 15 Nov is the real grade; this is the early read.
