"""Tests for the brain region resolving."""

import pytest
from scholarag.hierarchy_resolving import (
    RegionMeta,
    get_descendants_id,
    get_descendants_names,
)


@pytest.mark.parametrize(
    "brain_region_id,expected_descendants",
    [
        (68, {68}),
        (
            985,
            {
                320,
                648,
                844,
                882,
                943,
                985,
                3718675619,
                1758306548,
            },
        ),
        (
            369,
            {
                450,
                369,
                1026,
                854,
                577,
                625,
                945,
                1890964946,
                3693772975,
            },
        ),
        (
            178,
            {
                316,
                178,
                300,
                1043765183,
            },
        ),
        ("not-a-int", {"not-a-int"}),
    ],
)
def test_get_descendants(brain_region_id, expected_descendants, brain_region_json_path):
    descendants = get_descendants_id(brain_region_id, json_path=brain_region_json_path)
    assert expected_descendants == descendants


def test_get_descendants_errors(brain_region_json_path):
    brain_region_id = "1111111111"
    with pytest.raises(KeyError):
        get_descendants_id(brain_region_id, json_path=brain_region_json_path)


def test_RegionMeta_load_real_file(brain_region_json_path):
    RegionMeta_test = RegionMeta.load_config(brain_region_json_path)

    # check root.
    assert RegionMeta_test.root_id == 997
    assert RegionMeta_test.parent_id[997] == 0

    # check some names / st_levels.
    assert RegionMeta_test.name_[123] == "Koelliker-Fuse subnucleus"
    assert RegionMeta_test.name_[78] == "middle cerebellar peduncle"
    assert RegionMeta_test.st_level[55] == 10

    # check some random parents / childrens.
    assert RegionMeta_test.parent_id[12] == 165
    assert RegionMeta_test.parent_id[78] == 752
    assert RegionMeta_test.parent_id[700] == 88
    assert RegionMeta_test.parent_id[900] == 840
    assert RegionMeta_test.children_ids[12] == []
    assert RegionMeta_test.children_ids[23] == []
    assert RegionMeta_test.children_ids[670] == [2260827822, 3562104832]
    assert RegionMeta_test.children_ids[31] == [1053, 179, 227, 39, 48, 572, 739]


@pytest.mark.parametrize(
    "brain_region_name,expected_descendants_names",
    [
        ("rangom_name_not_in_list", ["rangom_name_not_in_list"]),
        (
            "primary motor area",
            [
                "primary motor area, layer 1",
                "primary motor area, layer 5",
                "primary motor area, layer 6a",
                "primary motor area, layer 6b",
                "primary motor area, layer 2/3",
                "primary motor area",
                "primary motor area, layer 2",
                "primary motor area, layer 3",
            ],
        ),
        (
            "primary somatosensory area, upper limb",
            [
                "primary somatosensory area, upper limb, layer 1",
                "primary somatosensory area, upper limb",
                "primary somatosensory area, upper limb, layer 6b",
                "primary somatosensory area, upper limb, layer 2/3",
                "primary somatosensory area, upper limb, layer 4",
                "primary somatosensory area, upper limb, layer 5",
                "primary somatosensory area, upper limb, layer 6a",
                "primary somatosensory area, upper limb, layer 3",
                "primary somatosensory area, upper limb, layer 2",
            ],
        ),
        (  # test with random uper cases
            "veNtral pArt of the lAteraL Geniculate Complex",
            [
                "ventral part of the lateral geniculate complex, medial zone",
                "ventral part of the lateral geniculate complex",
                "ventral part of the lateral geniculate complex, lateral zone",
                "ventral part of the lateral geniculate complex: other",
            ],
        ),
    ],
)
def test_get_descendants_names(
    brain_region_name, expected_descendants_names, brain_region_json_path
):
    descendants = get_descendants_names(
        brain_region_name, json_path=brain_region_json_path
    )
    assert sorted(expected_descendants_names) == sorted(descendants)
