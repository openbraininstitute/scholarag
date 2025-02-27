"""Hierarchy resolving utilies."""

import json
import logging
import numbers
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)


class RegionMeta:
    """Class holding the hierarchical region metadata.

    Typically, such information would be parsed from a `brain_regions.json`
    file.

    Parameters
    ----------
    background_id : int, optional
        Override the default ID for the background.
    """

    def __init__(self, background_id: int = 0) -> None:
        self.background_id = background_id
        self.root_id: int | None = None

        self.name_: dict[int, str] = {self.background_id: "background"}
        self.st_level: dict[int, int | None] = {self.background_id: None}

        self.parent_id: dict[int, int] = {self.background_id: background_id}
        self.children_ids: dict[int, list[int]] = {self.background_id: []}

    def children(self, region_id: int) -> tuple[int, ...]:
        """Get all child region IDs of a given region.

        Note that by children we mean only the direct children, much like
        by parent we only mean the direct parent. The cumulative quantities
        that span all generations are called ancestors and descendants.

        Parameters
        ----------
        region_id : int
            The region ID in question.

        Returns
        -------
        int
            The region ID of a child region.
        """
        return tuple(self.children_ids[region_id])

    def descendants(self, ids: int | list[int]) -> set[int]:
        """Find all descendants of given regions.

        The result is inclusive, i.e. the input region IDs will be
        included in the result.

        Parameters
        ----------
        ids : int or iterable of int
            A region ID or a collection of region IDs to collect
            descendants for.

        Returns
        -------
        set
            All descendant region IDs of the given regions, including the input
            regions themselves.
        """
        if isinstance(ids, numbers.Integral):
            unique_ids: set[int] = {ids}
        elif isinstance(ids, set):
            unique_ids = set(ids)

        def iter_descendants(region_id: int) -> Iterator[int]:
            """Iterate over all descendants of a given region ID.

            Parameters
            ----------
            region_id
                Integer representing the id of the region

            Returns
            -------
                Iterator with descendants of the region
            """
            yield region_id
            for child in self.children(region_id):
                yield child
                yield from iter_descendants(child)

        descendants = set()
        for id_ in unique_ids:
            descendants |= set(iter_descendants(id_))

        return descendants

    def save_config(self, json_file_path: str | Path) -> None:
        """Save the actual configuration in a json file.

        Parameters
        ----------
        json_file_path
            Path where to save the json file
        """
        to_save = {
            "root_id": self.root_id,
            "names": self.name_,
            "st_level": self.st_level,
            "parent_id": self.parent_id,
            "children_ids": self.children_ids,
        }
        with open(json_file_path, "w") as fs:
            fs.write(json.dumps(to_save))

    @classmethod
    def load_config(cls, json_file_path: str | Path) -> "RegionMeta":
        """Load a configuration in a json file and return a 'RegionMeta' instance.

        Parameters
        ----------
        json_file_path
            Path to the json file containing the brain region hierarchy

        Returns
        -------
            RegionMeta class with pre-loaded hierarchy
        """
        with open(json_file_path, "r") as fs:
            to_load = json.load(fs)

        # Needed to convert json 'str' keys to int.
        for k1 in to_load.keys():
            if not isinstance(to_load[k1], int):
                to_load[k1] = {int(k): v for k, v in to_load[k1].items()}

        self = cls()

        self.root_id = to_load["root_id"]
        self.name_ = to_load["names"]
        self.st_level = to_load["st_level"]
        self.parent_id = to_load["parent_id"]
        self.children_ids = to_load["children_ids"]

        return self


def load_names_mapping(json_path: Path | str) -> dict[int, str]:
    """Load the name to ID mapping of the Knowledge graph.

    Parameters
    ----------
    json_path : str or pathlib.Path

    Returns
    -------
    Dict
        name to ID mapping.
    """
    with open(json_path) as fh:
        KG_hierarchy = json.load(fh)

    for k1 in KG_hierarchy.keys():
        if not isinstance(KG_hierarchy[k1], int):
            KG_hierarchy[k1] = {int(k): v for k, v in KG_hierarchy[k1].items()}

    # return the lower case of id : "names"
    return {k: v.lower() for k, v in KG_hierarchy["names"].items()}


def get_descendants_id(brain_region_id: int, json_path: str | Path) -> set[int]:
    """Get all descendant of a brain region id.

    Parameters
    ----------
    brain_region_id
        Brain region ID to find descendants for.
    json_path
        Path to the json file containing the BR hierarchy

    Returns
    -------
        Set of descendants of a brain region
    """
    try:
        # Convert the id into an int
        brain_region_int = int(brain_region_id)

        # Get the descendant ids of this BR (as int).
        region_meta = RegionMeta.load_config(json_path)
        hierarchy = region_meta.descendants(brain_region_int)

    except ValueError:
        logger.info(
            f"The brain region {brain_region_id} didn't end with an int. Returning only"
            " the parent one."
        )
        hierarchy = {brain_region_id}
    except IOError:
        logger.warning(f"The file {json_path} doesn't exist.")
        hierarchy = {brain_region_id}

    return hierarchy


def get_descendants_names(incoming_region: str, json_path: str | Path) -> list[str]:
    """
    Transform a list of brain region names to descendant brain region names.

    Args:
        incoming_regions : Brain region name.

    Returns
    -------
        List[str]: List of brain region names corresponding to the "incoming_regions".
    """
    id_to_br = load_names_mapping(json_path)
    br_to_id = {name: id for id, name in id_to_br.items()}

    # Convert brain region names to IDs using the inverse mapping.
    region_id = br_to_id.get(incoming_region.lower())
    if not region_id:
        return [incoming_region]

    # Get descendant IDs.
    descendant_ids = get_descendants_id(region_id, json_path)

    # Convert descendant IDs back to brain region names.
    result_regions = [
        id_to_br[descendant_id]
        for descendant_id in descendant_ids
        if descendant_id in id_to_br
    ]

    if not result_regions:
        return [incoming_region]

    return result_regions
