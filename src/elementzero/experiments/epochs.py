"""Declared historical epochs of the EZ-B001 benchmark family.

One epoch is one AME transition: an earlier edition is the only allowed
training source, the later edition is truth that stays forbidden until every
prediction is sealed.

    EZ-B001-A : AME2003 -> AME2012
    EZ-B001-B : AME2012 -> AME2016
    EZ-B001-C : AME2016 -> AME2020

Only the source edition and the target identities change across epochs. Parser
semantics, target rule, model suite, hyperparameters, uncertainty method, and
metric definitions are shared (WO-07 section 2), which is what makes the three
results comparable as one series.

``created_at`` is pinned per epoch so a rerun of the same protocol on the same
sources reproduces byte-identical Atlas bundles and manifests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

BENCHMARK_FAMILY = "EZ-B001"

# AMDC mass-table download locations for the raw files (gitignored locally).
AMDC_URLS = {
    "AME2003": "https://amdc.impcas.ac.cn/masstables/Ame2003/mass.mas03",
    "AME2012": "https://amdc.impcas.ac.cn/masstables/Ame2012/mass.mas12",
    "AME2016": "https://amdc.impcas.ac.cn/masstables/Ame2016/mass16.txt",
    "AME2020": "https://amdc.impcas.ac.cn/masstables/Ame2020/mass_1.mas20.txt",
}

# Publications, not only the electronic files (WO-07 section 8).
AME_CITATIONS = {
    "AME2003": (
        "G. Audi, A.H. Wapstra, C. Thibault, "
        "'The AME2003 atomic mass evaluation (II). Tables, graphs and references', "
        "Nuclear Physics A 729 (2003) 337-676, doi:10.1016/j.nuclphysa.2003.11.003"
    ),
    "AME2012": (
        "M. Wang, G. Audi, A.H. Wapstra, F.G. Kondev, M. MacCormick, X. Xu, B. Pfeiffer, "
        "'The AME2012 atomic mass evaluation (II). Tables, graphs and references', "
        "Chinese Physics C 36 (2012) 1603-2014, doi:10.1088/1674-1137/36/12/003"
    ),
    "AME2016": (
        "M. Wang, G. Audi, F.G. Kondev, W.J. Huang, S. Naimi, X. Xu, "
        "'The AME2016 atomic mass evaluation (II). Tables, graphs and references', "
        "Chinese Physics C 41 (2017) 030003, doi:10.1088/1674-1137/41/3/030003"
    ),
    "AME2020": (
        "M. Wang, W.J. Huang, F.G. Kondev, G. Audi, S. Naimi, "
        "'The AME2020 atomic mass evaluation (II). Tables, graphs and references', "
        "Chinese Physics C 45 (2021) 030003, doi:10.1088/1674-1137/abddaf"
    ),
}

# Raw file names of every declared edition. A prediction workspace is refused if
# any of these truth file names is reachable from it.
EDITION_FILENAMES = {
    "AME2003": "mass.mas03",
    "AME2012": "mass.mas12",
    "AME2016": "mass16.txt",
    "AME2020": "mass_1.mas20.txt",
}


@dataclass(frozen=True)
class EpochSpec:
    """One preregistered historical transition."""

    experiment_id: str
    training_edition: str
    truth_edition: str
    created_at: str
    benchmark_family: str = BENCHMARK_FAMILY

    @property
    def training_relpath(self) -> str:
        return f"data/raw/amdc/{self.training_edition}/{EDITION_FILENAMES[self.training_edition]}"

    @property
    def truth_relpath(self) -> str:
        return f"data/raw/amdc/{self.truth_edition}/{EDITION_FILENAMES[self.truth_edition]}"

    @property
    def training_filename(self) -> str:
        return EDITION_FILENAMES[self.training_edition]

    @property
    def truth_filename(self) -> str:
        return EDITION_FILENAMES[self.truth_edition]

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "benchmark_family": self.benchmark_family,
            "training_edition": self.training_edition,
            "truth_edition": self.truth_edition,
            "training_relpath": self.training_relpath,
            "truth_relpath": self.truth_relpath,
            "training_source_uri": AMDC_URLS[self.training_edition],
            "truth_source_uri": AMDC_URLS[self.truth_edition],
            "training_citation": AME_CITATIONS[self.training_edition],
            "truth_citation": AME_CITATIONS[self.truth_edition],
            "created_at": self.created_at,
        }


EPOCHS: dict[str, EpochSpec] = {
    "EZ-B001-A": EpochSpec(
        experiment_id="EZ-B001-A",
        training_edition="AME2003",
        truth_edition="AME2012",
        created_at="2026-08-16T00:00:00Z",
    ),
    "EZ-B001-B": EpochSpec(
        experiment_id="EZ-B001-B",
        training_edition="AME2012",
        truth_edition="AME2016",
        created_at="2026-08-16T01:00:00Z",
    ),
    "EZ-B001-C": EpochSpec(
        experiment_id="EZ-B001-C",
        training_edition="AME2016",
        truth_edition="AME2020",
        created_at="2026-08-16T02:00:00Z",
    ),
}

EPOCH_ORDER: tuple[str, ...] = ("EZ-B001-A", "EZ-B001-B", "EZ-B001-C")


def epoch_for(experiment_id: str) -> EpochSpec:
    try:
        return EPOCHS[experiment_id]
    except KeyError as exc:
        raise ValueError(
            f"unknown experiment {experiment_id!r}; declared epochs are {sorted(EPOCHS)}"
        ) from exc


def truth_filenames() -> tuple[str, ...]:
    """Every known raw truth file name, used by the blind-workspace preflight."""
    return tuple(sorted(EDITION_FILENAMES.values()))
