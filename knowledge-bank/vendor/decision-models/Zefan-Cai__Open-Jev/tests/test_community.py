import copy
import unittest

from jev.api import compile_request, format_response
from jev.community import (browser_proposal, browser_request, drone_proposal,
                           drone_request, example_requests, heist_proposal,
                           heist_request, pokemon_proposal, pokemon_request,
                           runescape_proposal, runescape_request)


def reference_response(request, selections=None):
    selections = selections or {}
    records = compile_request(request["state"], request["questions"])
    rows = []
    for record in records:
        selected = selections.get(record["id"], record["answer_keys"][0])
        rows.append([float(key == selected) for key in record["answer_keys"]])
    return format_response(records, rows)


class CommunityTest(unittest.TestCase):
    def setUp(self):
        self.examples = example_requests()

    def test_every_example_compiles_and_declared_field_scales_are_exact(self):
        for request in self.examples.values():
            compile_request(request["state"], request["questions"])
        self.assertEqual(len(self.examples), 9)
        for name in ("fraud_4", "code_security_4"):
            self.assertEqual(len(self.examples[name]["questions"]), 4)
        self.assertEqual(len(self.examples["support_28"]["questions"]), 28)
        records = compile_request(**self.examples["tariff_255"])
        self.assertEqual(len(records[0]["options"]), 255)
        self.assertIn("not real tariff codes", self.examples["tariff_255"]["state"]["notice"])

    def test_browser_resolves_only_supplied_text_and_observed_target(self):
        request = self.examples["browser"]
        response = reference_response(request, {"operation": "TYPE_TEXT", "type_text_target": "search-box", "text_value_0": "green-tea"})
        proposal = browser_proposal(request, response, current_snapshot_id="local-dom-17")
        self.assertEqual(proposal, {"snapshot_id": "local-dom-17", "operation": "TYPE_TEXT", "target_id": "search-box", "value_id": "green-tea", "text": "green tea"})
        self.assertNotIn("selector", proposal)

    def test_browser_rejects_stale_revision_before_postprocessing(self):
        request = self.examples["browser"]
        response = reference_response(request)
        for current in ("new-dom-18", ""):
            with self.assertRaises(ValueError):
                browser_proposal(request, response, current_snapshot_id=current)

    def test_browser_does_not_offer_arbitrary_text_generation(self):
        snapshot = self.examples["browser"]["state"]["snapshot"]
        request = browser_request("Search", snapshot)
        self.assertNotIn("TYPE_TEXT", request["questions"]["operation"]["criteria"])
        self.assertNotIn("type_text_target", request["questions"])
        for text_candidates in ({"missing": {"x": "anything"}}, {"search-button": {"x": "anything"}}, {"search-box": {}}):
            with self.assertRaises(ValueError):
                browser_request("Search", snapshot, text_candidates)

    def test_browser_select_options_and_click_ids_remain_observed(self):
        request = self.examples["browser"]
        response = reference_response(request, {"operation": "SELECT", "select_target": "sort", "select_value_0": "price"})
        self.assertEqual(browser_proposal(request, response, current_snapshot_id="local-dom-17")["option_id"], "price")
        response["answers"]["select_value_0"]["choice"] = "unobserved-option"
        with self.assertRaises(ValueError):
            browser_proposal(request, response, current_snapshot_id="local-dom-17")

    def test_browser_rejects_missing_and_duplicate_observations(self):
        snapshot = copy.deepcopy(self.examples["browser"]["state"]["snapshot"])
        snapshot["elements"].append(copy.deepcopy(snapshot["elements"][0]))
        with self.assertRaises(ValueError):
            browser_request("Search", snapshot)
        with self.assertRaises(ValueError):
            browser_request("Search", {"snapshot_id": "x"})

    def test_runescape_keeps_catalog_and_poll_intervals_closed(self):
        request = self.examples["runescape"]
        response = reference_response(request, {"next_action": "fish-spott1", "this_tick": "do_nothing", "poll_again_in_ticks": "5"})
        self.assertEqual(runescape_proposal(request, response), {"action_id": "fish-spott1", "tick_action": "do_nothing", "poll_again_in_ticks": 5})
        args = (request["state"]["observation"], request["questions"]["next_action"]["criteria"])
        with self.assertRaises(ValueError):
            runescape_request(*args, legal_tick_actions={"teleport": "Teleport anywhere"})
        with self.assertRaises(ValueError):
            runescape_request(*args, legal_tick_actions={"do_nothing": "Wait"}, poll_intervals=[0])

    def test_pokemon_faint_forecast_is_conditioned_on_selected_move(self):
        request = self.examples["pokemon"]
        response = reference_response(request, {"action": "move-scratch", "opponent_faints_0": "true", "opponent_faints_1": "false"})
        self.assertEqual(pokemon_proposal(request, response), {"action_id": "move-scratch", "opponent_faint_probability": 1})
        response = reference_response(request, {"action": "move-growl", "opponent_faints_0": "true", "opponent_faints_1": "false"})
        self.assertEqual(pokemon_proposal(request, response)["opponent_faint_probability"], 0)
        observation = copy.deepcopy(request["state"]["observation"])
        observation.pop("opponent")
        with self.assertRaises(ValueError):
            pokemon_request(observation, {"scratch": "Scratch"})
        observation["phase"] = "overworld"
        request = pokemon_request(observation, {"up": "Walk up"})
        self.assertEqual(set(request["questions"]), {"action"})

    def test_heist_uses_one_guards_local_observation_and_allows_no_target(self):
        request = self.examples["heist"]
        self.assertEqual(len(request["questions"]), 4)
        result = heist_proposal(request, reference_response(request))
        self.assertEqual(result["guard_id"], "guard-2")
        self.assertIsNone(result["target_id"])
        empty = heist_request(request["state"]["observation"], {"observe": "Observe"}, {})
        self.assertEqual(set(empty["questions"]["target"]["criteria"]), {"none"})
        with self.assertRaises(ValueError):
            heist_request(request["state"]["observation"], {}, {})

    def test_drone_requires_verified_climb_clearance_and_never_motor_commands(self):
        request = self.examples["drone"]
        observation = request["state"]["observation"]
        with self.assertRaises(ValueError):
            drone_request(observation, ["climb"])
        observation = copy.deepcopy(observation)
        observation["flight"]["climb_clearance_verified"] = True
        request = drone_request(observation, ["climb", "brake"])
        result = drone_proposal(request, reference_response(request, {"maneuver": "climb"}))
        self.assertEqual(result["maneuver"], "climb")
        self.assertEqual(set(result), {"maneuver", "risk", "target_lost_probability"})

    def test_malformed_responses_cannot_become_proposals(self):
        request = self.examples["drone"]
        good = reference_response(request)
        for mutate in (lambda a: a.pop("risk"), lambda a: a["risk"].update(score=float("nan")),
                       lambda a: a["target_truly_lost"].update(noul=2),
                       lambda a: a["maneuver"]["probabilities"].update(teleport=1),
                       lambda a: a["maneuver"].update(choice="brake")):
            response = copy.deepcopy(good)
            mutate(response["answers"])
            with self.assertRaises(ValueError):
                drone_proposal(request, response)
        with self.assertRaises(ValueError):
            heist_proposal(request, good)

    def test_builders_reject_empty_observations(self):
        calls = [lambda: runescape_request({}, {"wait": "Wait"}, legal_tick_actions={"do_nothing": "Wait"}),
                 lambda: pokemon_request({}, {"up": "Up"}),
                 lambda: heist_request({}, {"observe": "Observe"}, {}),
                 lambda: drone_request({}, ["brake"])]
        for call in calls:
            with self.assertRaises(ValueError):
                call()


if __name__ == "__main__":
    unittest.main()
