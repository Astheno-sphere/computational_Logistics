# -*- coding: utf-8 -*-
# Copyright (C) 2021 GIS OPS UG
#
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations under
# the License.
#
"""Tests for the IGN Geoportail module."""

from copy import deepcopy

import responses

import tests as _test
from routingpy import IGN
from routingpy.direction import Direction
from routingpy.isochrone import Isochrone, Isochrones
from tests.data.mock import *


class IGNTest(_test.TestCase):
    name = "ign"

    def setUp(self):
        self.client = IGN()

    @responses.activate
    def test_directions_geojson(self):
        """Test directions with GeoJSON geometry format."""
        query = deepcopy(ENDPOINTS_QUERIES[self.name]["directions"])

        responses.add(
            responses.GET,
            "https://data.geopf.fr/navigation/itineraire",
            status=200,
            json=ENDPOINTS_RESPONSES["ign"]["directions_geojson"],
            content_type="application/json",
        )

        route = self.client.directions(**query)

        self.assertEqual(1, len(responses.calls))
        self.assertIsInstance(route, Direction)
        self.assertIsInstance(route.distance, int)
        self.assertIsInstance(route.duration, int)
        self.assertIsInstance(route.geometry, list)
        self.assertIsInstance(route.raw, dict)

    @responses.activate
    def test_directions_polyline(self):
        """Test directions with Polyline geometry format."""
        query = deepcopy(ENDPOINTS_QUERIES[self.name]["directions"])
        query["geometry_format"] = "polyline"

        responses.add(
            responses.GET,
            "https://data.geopf.fr/navigation/itineraire",
            status=200,
            json=ENDPOINTS_RESPONSES["ign"]["directions_polyline"],
            content_type="application/json",
        )

        route = self.client.directions(**query)

        self.assertEqual(1, len(responses.calls))
        self.assertIsInstance(route, Direction)
        self.assertIsInstance(route.distance, int)
        self.assertIsInstance(route.duration, int)
        self.assertIsInstance(route.geometry, list)
        self.assertIsInstance(route.raw, dict)

    @responses.activate
    def test_directions_with_intermediates(self):
        """Test directions with intermediate waypoints."""
        query = deepcopy(ENDPOINTS_QUERIES[self.name]["directions"])
        query["locations"][1:1] = [[8.7, 49.42], [8.73, 49.43]]

        responses.add(
            responses.GET,
            "https://data.geopf.fr/navigation/itineraire",
            status=200,
            json=ENDPOINTS_RESPONSES["ign"]["directions_geojson"],
            content_type="application/json",
        )

        route = self.client.directions(**query)

        self.assertEqual(1, len(responses.calls))
        self.assertIsInstance(route, Direction)
        self.assertIsInstance(route.distance, int)

    @responses.activate
    def test_full_isochrones(self):
        """Test isochrones calculation."""
        query = deepcopy(ENDPOINTS_QUERIES[self.name]["isochrones"])

        responses.add(
            responses.GET,
            "https://data.geopf.fr/navigation/isochrone",
            status=200,
            json=ENDPOINTS_RESPONSES["ign"]["isochrones"],
            content_type="application/json",
        )

        isochrones = self.client.isochrones(**query)

        self.assertEqual(1, len(responses.calls))
        self.assertIsInstance(isochrones, Isochrones)
        for iso in isochrones:
            self.assertIsInstance(iso, Isochrone)
            self.assertIsInstance(iso.geometry, (list, dict))

    @responses.activate
    def test_isochrones_distance_type(self):
        """Test isochrones with distance-based intervals."""
        query = deepcopy(ENDPOINTS_QUERIES[self.name]["isochrones"])
        query["interval_type"] = "distance"

        responses.add(
            responses.GET,
            "https://data.geopf.fr/navigation/isochrone",
            status=200,
            json=ENDPOINTS_RESPONSES["ign"]["isochrones"],
            content_type="application/json",
        )

        isochrones = self.client.isochrones(**query)

        self.assertEqual(1, len(responses.calls))
        self.assertIsInstance(isochrones, Isochrones)

    @responses.activate
    def test_isochrones_with_constraints(self):
        """Test isochrones with routing constraints."""
        query = deepcopy(ENDPOINTS_QUERIES[self.name]["isochrones"])
        query["constraints"] = {"avoid": ["toll"]}

        responses.add(
            responses.GET,
            "https://data.geopf.fr/navigation/isochrone",
            status=200,
            json=ENDPOINTS_RESPONSES["ign"]["isochrones"],
            content_type="application/json",
        )

        isochrones = self.client.isochrones(**query)

        self.assertEqual(1, len(responses.calls))
        self.assertIsInstance(isochrones, Isochrones)
