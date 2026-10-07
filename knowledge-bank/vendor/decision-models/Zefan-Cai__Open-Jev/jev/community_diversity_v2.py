"""Original, rule-verifiable community decision scenarios; no benchmark inputs.

The 80 policy families are authored here. X links identify use-case inspiration,
not imported examples or annotations. Run ``python -m jev.community_diversity_v2``.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import copy
import hashlib
import itertools
import json
from pathlib import Path
import random

from .data import _hash, _write_dataset, validate_records


VERSION = "community-diversity-v2"
SPLIT_POLICY = "authored_policy_family_disjoint_6_train_1_calibration_1_validation_1_test_1_ood"
SOURCES = {
    "support": ["https://x.com/aad34210/status/2101837143576662211"],
    "ir": ["https://x.com/ShengyaoZhuang/status/2101212268440723895"],
    "contracts": ["https://x.com/matu79go/status/2101878714917429488"],
    "rag": ["https://github.com/emretheus/jev-rag-benchmark"],
    "browser_tools": ["https://x.com/gregpr07/status/2100411066966749359"],
    "shell_history": ["https://x.com/khajanpandey/status/2101837339387437384"],
    "games": ["https://x.com/loktar00/status/2101851403790512615", "https://x.com/edwartnoyola/status/2101799243811876866"],
    "rubric_judge": ["https://x.com/HamelHusain/status/2101533413010440593"],
}
RANKS = {"support": ("response_minutes", "min"), "ir": ("publication_day", "max"),
         "contracts": ("section_number", "min"), "rag": ("source_revision", "max"),
         "browser_tools": ("interaction_count", "min"), "shell_history": ("history_sequence", "max"),
         "games": ("completion_ticks", "min"), "rubric_judge": ("response_words", "min")}


def E(op, *args):
    return (op, *args)


def policies():
    """Ten distinct decision specifications per domain, fixed before generation."""
    result = []

    def add(domain, name, setting, checks, params=None):
        result.append({"domain": domain, "name": name, "setting": setting,
                       "checks": checks, "parameters": params or {}, "rank": RANKS[domain]})

    # Support: separate ordered/exception policies, not translations counted as domains.
    add("support", "refund_window", "Select an admissible refund handling plan for a returned purchase.", [
        E("le", "$days_since_delivery", "@window_days"), E("eq", "$payment_settled", True),
        E("not", E("eq", "$refund_already_paid", True)), E("or", E("eq", "$seal_intact", True), E("eq", "$defect_confirmed", True))], {"window_days": [7, 14, 30]})
    add("support", "warranty_repair", "Decide which proposed warranty repair can be authorized.", [
        E("le", "$months_owned", "@warranty_months"), E("eq", "$serial_matches_receipt", True),
        E("implies", E("eq", "$liquid_damage", True), E("eq", "$accidental_cover", True)), E("ne", "$diagnosis", "consumable_wear")], {"warranty_months": [12, 18, 24]})
    add("support", "delayed_parcel", "Choose a supported replacement shipment rather than treating any delay as loss.", [
        E("gt", "$days_since_last_scan", "@scan_limit"), E("eq", "$delivery_signature_present", False),
        E("or", E("eq", "$carrier_loss_confirmed", True), E("ge", "$days_over_promise", 5)), E("eq", "$address_verified", True)], {"scan_limit": [3, 5, 8]})
    add("support", "account_recovery", "Select an account recovery route with sufficient independent identity evidence.", [
        E("ge", E("add", "$verified_identity_factors", "$verified_ownership_factors"), 3), E("ge", "$verified_identity_factors", 1),
        E("eq", "$recovery_channel_compromised", False), E("implies", E("eq", "$administrator_account", True), E("eq", "$manager_approval", True))])
    add("support", "subscription_cancellation", "Choose a cancellation plan respecting notice, billing and an explicit cooling-off exception.", [
        E("or", E("ge", "$notice_days", "@notice_required"), E("le", "$days_since_signup", 2)), E("eq", "$customer_authenticated", True),
        E("le", "$refund_cents", "$unconsumed_credit_cents"), E("eq", "$renewal_after_cancellation", False)], {"notice_required": [5, 10, 14]})
    add("support", "duplicate_charge", "Select a defensible duplicate-charge reversal without reversing a merely pending authorization.", [
        E("eq", "$merchant_reference", "$other_merchant_reference"), E("eq", "$amount_cents", "$other_amount_cents"),
        E("and", E("eq", "$both_charges_posted", True), E("ne", "$charge_id", "$other_charge_id")), E("le", E("abs", E("sub", "$charge_day", "$other_charge_day")), 2)])
    add("support", "partial_return", "Choose a partial-return payout that accounts for kept goods and a bundle discount.", [
        E("le", "$returned_units", "$purchased_units"), E("gt", "$returned_units", 0),
        E("le", "$payout_cents", E("sub", "$returned_value_cents", "$lost_bundle_discount_cents")), E("implies", E("eq", "$hygiene_item", True), E("eq", "$sealed", True))])
    add("support", "damaged_order", "Route a damaged-order complaint; safety hazards require specialist authority even for small amounts.", [
        E("eq", "$damage_evidence_received", True), E("le", "$claim_days", "@claim_window"),
        E("implies", E("eq", "$electrical_hazard", True), E("eq", "$specialist_authorized", True)), E("or", E("eq", "$replacement_in_stock", True), E("eq", "$refund_available", True))], {"claim_window": [10, 20, 30]})
    add("support", "outage_compensation", "Choose an outage compensation plan with a duration threshold and an exclusion override.", [
        E("ge", "$outage_minutes", "@minimum_outage"), E("eq", "$affected_service", "$subscribed_service"),
        E("or", E("eq", "$scheduled_maintenance", False), E("eq", "$maintenance_notice_missing", True)), E("le", "$credit_cents", "$monthly_fee_cents")], {"minimum_outage": [30, 60, 120]})
    add("support", "privacy_export", "Select a permissible personal-data export route without treating an unverified request as consent.", [
        E("eq", "$requester_identity_verified", True), E("has", "$export_fields", "own_records"),
        E("not", E("has", "$export_fields", "other_customers")), E("implies", E("eq", "$delegate_request", True), E("eq", "$delegation_document_valid", True))])

    # Retrieval: hard negatives differ in scope, version, quantities or requested evidence.
    add("ir", "hardware_manual", "Rerank manuals for the exact hardware revision and both requested operating limits.", [
        E("eq", "$device_revision", "@revision"), E("has", "$covered_fields", "operating_voltage"), E("has", "$covered_fields", "temperature_limit"),
        E("and", E("eq", "$withdrawn", False), E("eq", "$manufacturer_document", True))], {"revision": [2, 4, 7]})
    add("ir", "release_migration", "Find release notes that apply to the requested upgrade edge, not just either endpoint.", [
        E("eq", "$from_version", "@from_version"), E("eq", "$to_version", "@to_version"),
        E("has", "$sections", "breaking_changes"), E("or", E("eq", "$migration_tested", True), E("eq", "$official_upgrade_path", True))], {"from_version": [2, 5, 8], "to_version": [10, 12, 15]})
    add("ir", "regional_returns", "Retrieve an applicable returns policy rather than a similarly worded policy for another region or item category.", [
        E("eq", "$region", "@region"), E("eq", "$item_category", "@category"), E("le", "$effective_from_day", "@query_day"),
        E("or", E("eq", "$no_expiry", True), E("ge", "$effective_until_day", "@query_day"))], {"region": ["north", "south", "west"], "category": ["furniture", "electronics", "books"], "query_day": [40, 80, 120]})
    add("ir", "connecting_route", "Rank journey documents that establish a legal two-leg connection, including its transfer buffer.", [
        E("eq", "$first_arrival_station", "$second_departure_station"), E("ge", E("sub", "$second_departure_minute", "$first_arrival_minute"), 5),
        E("le", "$changes", "@maximum_changes"), E("eq", "$service_runs_on_query_day", True)], {"maximum_changes": [1, 2, 3]})
    add("ir", "study_population", "Retrieve a study answering the requested population and measured endpoint instead of a related mechanistic discussion.", [
        E("eq", "$population", "@population"), E("has", "$measured_endpoints", "primary_endpoint"),
        E("ge", "$participants", "@minimum_sample"), E("not", E("or", E("eq", "$retracted", True), E("eq", "$editorial_only", True)))], {"population": ["adults", "adolescents", "older_adults"], "minimum_sample": [20, 40, 60]})
    add("ir", "inventory_answer", "Find inventory evidence for the exact SKU and warehouse with enough unreserved stock.", [
        E("eq", "$sku", "@sku"), E("eq", "$warehouse", "@warehouse"), E("ge", E("sub", "$on_hand", "$reserved"), "@needed"),
        E("le", "$snapshot_age_minutes", 15)], {"sku": ["cable_A", "adapter_B", "sensor_C"], "warehouse": ["east", "central", "west"], "needed": [2, 5, 8]})
    add("ir", "incident_runbook", "Select a runbook matching the error, topology and diagnostic preconditions.", [
        E("eq", "$error_code", "@error_code"), E("eq", "$topology", "@topology"), E("has", "$verified_checks", "network_reachable"),
        E("implies", E("eq", "$destructive_repair", True), E("has", "$verified_checks", "backup_verified"))], {"error_code": ["E17", "E42", "E65"], "topology": ["single", "replicated", "sharded"]})
    add("ir", "access_schedule", "Retrieve a schedule proving access at the requested time and for the requested visitor class.", [
        E("le", "$opens_at", "@visit_time"), E("gt", "$closes_at", "@visit_time"), E("has", "$allowed_classes", "@visitor_class"),
        E("eq", "$exceptional_closure", False)], {"visit_time": [9, 13, 17], "visitor_class": ["student", "researcher", "public"]})
    add("ir", "warranty_transfer", "Find warranty text that actually covers transfer to a second owner, with required registration evidence.", [
        E("eq", "$transfer_allowed", True), E("le", "$owner_count", "$maximum_owners"),
        E("implies", E("eq", "$registration_required", True), E("eq", "$registration_procedure_present", True)), E("has", "$document_sections", "remaining_term")])
    add("ir", "api_auth_migration", "Rerank documentation for an authentication migration including scopes, sunset timing and replacement endpoint.", [
        E("eq", "$legacy_scheme", "@scheme"), E("has", "$provided_details", "replacement_endpoint"), E("has", "$provided_details", "required_scopes"),
        E("and", E("ge", "$sunset_day", "@migration_day"), E("eq", "$draft_only", False))], {"scheme": ["basic", "legacy_token", "session_cookie"], "migration_day": [30, 60, 90]})

    # Contract candidates are explicit clause records. These are not CUAD span labels.
    add("contracts", "noncompete_scope", "Identify an operative non-compete clause with bounded duration and territory.", [
        E("eq", "$clause_kind", "noncompete"), E("and", E("eq", "$executed", True), E("eq", "$waived", False)),
        E("le", "$restriction_months", "@maximum_months"), E("has", "$specified_terms", "territory")], {"maximum_months": [6, 12, 18]})
    add("contracts", "automatic_renewal", "Identify an enforceable automatic-renewal clause with a real opt-out route and enough notice.", [
        E("eq", "$automatic_renewal", True), E("gt", "$renewal_months", 0), E("has", "$notice_methods", "written_notice"),
        E("ge", E("sub", "$renewal_day", "$opt_out_deadline"), "@notice_days")], {"notice_days": [15, 30, 45]})
    add("contracts", "audit_right", "Find an audit-right clause permitting the requested reviewer while protecting unrelated customer records.", [
        E("has", "$permitted_auditors", "@auditor"), E("ge", "$notice_days", 5), E("not", E("has", "$accessible_records", "unrelated_customers")),
        E("or", E("eq", "$annual_audits_used", 0), E("eq", "$suspected_breach_exception", True))], {"auditor": ["customer", "independent_auditor", "regulator"]})
    add("contracts", "liability_cap", "Locate a liability limitation that covers ordinary claims while preserving the specified carve-outs.", [
        E("ge", "$cap_cents", "$annual_fees_cents"), E("has", "$carve_outs", "fraud"), E("has", "$carve_outs", "intentional_misconduct"),
        E("not", E("eq", "$cap_disclaimed_in_amendment", True))])
    add("contracts", "assignment_consent", "Determine which assignment clause supports this transaction, including an affiliate exception.", [
        E("or", E("eq", "$written_consent", True), E("and", E("eq", "$affiliate_transfer", True), E("eq", "$affiliate_exception", True))),
        E("eq", "$assignee_assumes_obligations", True), E("eq", "$assignor_released_without_permission", False), E("le", "$notice_delay_days", 10)])
    add("contracts", "confidentiality_survival", "Find a confidentiality clause with the required exclusions and obligations surviving expiry.", [
        E("ge", "$survival_years", "@required_years"), E("has", "$exclusions", "already_public"),
        E("has", "$exclusions", "independently_developed"), E("implies", E("eq", "$compelled_disclosure", True), E("eq", "$notice_if_lawful", True))], {"required_years": [2, 3, 5]})
    add("contracts", "termination_cure", "Identify a termination provision whose cure opportunity has actually expired without a cure.", [
        E("ge", E("sub", "$decision_day", "$notice_received_day"), "$cure_period_days"), E("eq", "$material_breach", True),
        E("eq", "$breach_cured", False), E("eq", "$notice_method", "contractual_method")])
    add("contracts", "governing_law_venue", "Find the controlling law-and-venue provision after reconciling the signed amendment hierarchy.", [
        E("eq", "$jurisdiction", "@jurisdiction"), E("eq", "$forum", "@forum"), E("eq", "$superseded", False),
        E("or", E("eq", "$in_signed_master", True), E("and", E("eq", "$in_amendment", True), E("eq", "$amendment_signed_by_both", True)))], {"jurisdiction": ["Ontario", "Oregon", "Scotland"], "forum": ["arbitration", "local_courts", "commercial_court"]})
    add("contracts", "exclusivity_exception", "Classify a qualified exclusivity obligation with a channel-specific exception.", [
        E("eq", "$exclusive_supply", True), E("has", "$covered_channels", "@channel"),
        E("not", E("has", "$excepted_channels", "@channel")), E("ge", "$minimum_volume", "@volume")], {"channel": ["retail", "enterprise", "online"], "volume": [10, 20, 40]})
    add("contracts", "change_of_control", "Identify a valid change-of-control notification clause and its termination trigger.", [
        E("gt", "$voting_share_percent", 50), E("le", "$notification_delay_days", "@deadline"),
        E("implies", E("eq", "$acquirer_is_competitor", True), E("eq", "$termination_right_express", True)), E("eq", "$mere_asset_sale_only", False)], {"deadline": [10, 20, 30]})

    # Grounding families distinguish evidence absence, conflict, joins and temporal scope.
    add("rag", "two_hop_ownership", "Select evidence that supports a two-hop ownership conclusion with a matching intermediate entity.", [
        E("eq", "$first_edge_target", "$second_edge_subject"), E("eq", "$first_edge_relation", "owns"),
        E("eq", "$second_edge_relation", "controls"), E("and", E("eq", "$first_edge_asserted", True), E("eq", "$second_edge_asserted", True))])
    add("rag", "temporal_fact", "Ground an answer in a record valid at the question time rather than the newest publication alone.", [
        E("le", "$valid_from", "@question_day"), E("gt", "$valid_until", "@question_day"), E("eq", "$subject", "@subject"),
        E("eq", "$record_retracted", False)], {"question_day": [30, 60, 90], "subject": ["harbor", "depot", "station"]})
    add("rag", "contradiction_resolution", "Use a conflict-resolution policy requiring both authority and an explicit superseding record.", [
        E("ge", "$authority_level", "@minimum_authority"), E("eq", "$supersedes_record", "$conflicting_record"),
        E("gt", "$revision", "$conflicting_revision"), E("eq", "$unresolved_same_rank_conflict", False)], {"minimum_authority": [2, 3, 4]})
    add("rag", "numerical_claim", "Check a claimed total against two grounded components and an explicit unit match.", [
        E("eq", "$claimed_total", E("add", "$component_a", "$component_b")), E("eq", "$unit_a", "$unit_b"),
        E("eq", "$claim_unit", "$unit_a"), E("and", E("eq", "$component_a_sourced", True), E("eq", "$component_b_sourced", True))])
    add("rag", "citation_coverage", "Choose a response whose citations cover every required factual component and actually support those components.", [
        E("has", "$cited_claims", "identity"), E("has", "$cited_claims", "date"), E("has", "$cited_claims", "quantity"),
        E("and", E("eq", "$citation_entails_claims", True), E("eq", "$fabricated_citation", False))])
    add("rag", "negative_evidence", "Ground a negative claim only when a complete search over the correct scope supplies explicit exclusion evidence.", [
        E("eq", "$search_scope", "@scope"), E("eq", "$search_complete", True), E("eq", "$explicit_absence_record", True),
        E("eq", "$positive_counterexample_found", False)], {"scope": ["signed_contracts", "current_orders", "published_releases"]})
    add("rag", "entity_alias_chain", "Resolve an alias using a documented alias edge and a same-entity fact, not a string similarity guess.", [
        E("eq", "$alias_target_id", "$fact_subject_id"), E("eq", "$alias_type", "verified_alias"),
        E("eq", "$fact_relation", "@relation"), E("ne", "$alias_source_id", "$unrelated_entity_id")], {"relation": ["headquarters", "founded_on", "operates_in"]})
    add("rag", "policy_exception", "Ground a policy answer by combining the general rule with the applicable, current exception.", [
        E("eq", "$general_rule_active", True), E("implies", E("eq", "$exception_conditions_met", True), E("eq", "$exception_applied", True)),
        E("implies", E("eq", "$exception_applied", True), E("eq", "$exception_record_current", True)), E("eq", "$unsupported_extra_condition", False)])
    add("rag", "independent_sources", "Select support from sufficiently many independent source organizations, not duplicated syndications.", [
        E("ge", "$independent_organizations", "@minimum_sources"), E("le", "$independent_organizations", "$documents"),
        E("eq", "$all_sources_traceable", True), E("eq", "$shared_unverified_origin", False)], {"minimum_sources": [2, 3, 4]})
    add("rag", "qualified_comparison", "Ground a comparative claim only when measurements share units, population and observation period.", [
        E("eq", "$left_unit", "$right_unit"), E("eq", "$left_population", "$right_population"),
        E("eq", "$left_period", "$right_period"), E("gt", "$left_measurement", "$right_measurement")])

    # Dynamic browser/tool candidates carry current state, capabilities and arguments.
    add("browser_tools", "stale_dom", "Choose a current DOM click target rather than a stale or disabled element with matching text.", [
        E("eq", "$dom_revision", "@current_revision"), E("eq", "$enabled", True), E("eq", "$visible", True),
        E("eq", "$accessible_name", "@goal_name")], {"current_revision": [3, 8, 13], "goal_name": ["Continue", "Save draft", "Show details"]})
    add("browser_tools", "typing_fallback", "Choose an input action whose value and fallback preserve the requested text exactly.", [
        E("eq", "$text_value", "@requested_value"), E("eq", "$input_read_only", False), E("eq", "$field_role", "textbox"),
        E("or", E("eq", "$fill_supported", True), E("and", E("eq", "$typing_supported", True), E("eq", "$clear_before_typing", True)))], {"requested_value": ["A-17", "B 42", "code_9"]})
    add("browser_tools", "pagination", "Choose a pagination action that advances the cursor without repeating a page or leaving the requested filter.", [
        E("ne", "$next_cursor", "$current_cursor"), E("eq", "$filter_hash", "@filter_hash"), E("eq", "$next_link_disabled", False),
        E("not", E("has", "$visited_cursors", "$next_cursor"))], {"filter_hash": ["open_tickets", "recent_invoices", "active_projects"]})
    add("browser_tools", "date_range_form", "Select a date-range submission with ordered dates and the requested timezone.", [
        E("le", "$start_day", "$end_day"), E("le", E("sub", "$end_day", "$start_day"), "@maximum_range"),
        E("eq", "$timezone", "@timezone"), E("eq", "$validation_errors", 0)], {"maximum_range": [7, 14, 30], "timezone": ["UTC", "Asia/Tokyo", "America/Chicago"]})
    add("browser_tools", "upload_constraint", "Choose an upload operation that meets file size, type and target-folder constraints.", [
        E("le", "$file_bytes", "@maximum_bytes"), E("in", "$mime_type", ["application/pdf", "text/plain"]),
        E("eq", "$target_folder", "@folder"), E("eq", "$upload_control_enabled", True)], {"maximum_bytes": [20, 40, 80], "folder": ["drafts", "receipts", "exports"]})
    add("browser_tools", "tool_scope", "Select a catalog tool whose capability and authorization scope cover the request without an unwanted write.", [
        E("has", "$capabilities", "@needed_capability"), E("has", "$granted_scopes", "@needed_scope"),
        E("eq", "$writes_remote_state", False), E("eq", "$endpoint_available", True)], {"needed_capability": ["search", "list", "inspect"], "needed_scope": ["project_read", "billing_read", "profile_read"]})
    add("browser_tools", "argument_binding", "Pick an action whose object ID, workspace and argument type match the current task.", [
        E("eq", "$object_id", "@object_id"), E("eq", "$workspace_id", "@workspace_id"),
        E("eq", "$argument_type", "integer"), E("and", E("ge", "$argument_value", 1), E("le", "$argument_value", 5))], {"object_id": [11, 23, 37], "workspace_id": [2, 4, 6]})
    add("browser_tools", "idempotent_retry", "Select a retry plan after an ambiguous write response without duplicating the transaction.", [
        E("eq", "$idempotency_key", "$original_idempotency_key"), E("eq", "$payload_hash", "$original_payload_hash"),
        E("or", E("eq", "$previous_result_unknown", True), E("eq", "$previous_attempt_not_started", True)), E("eq", "$server_supports_idempotency", True)])
    add("browser_tools", "goal_completion", "Select a completion claim based on persisted state, not a transient notification.", [
        E("eq", "$persisted_value", "@goal_value"), E("eq", "$refresh_confirmed", True), E("eq", "$unsaved_changes", False),
        E("eq", "$validation_error_visible", False)], {"goal_value": ["enabled", "archived", "scheduled"]})
    add("browser_tools", "confirmation_gate", "Choose a browser action with the required confirmation for consequential changes and the correct preview.", [
        E("implies", E("eq", "$consequential_change", True), E("eq", "$explicit_confirmation", True)), E("eq", "$preview_target", "$actual_target"),
        E("eq", "$session_expired", False), E("eq", "$form_revision", "$preview_revision")])

    # These are generated command-history attributes, never private shell histories.
    add("shell_history", "exact_repo_test", "Rank remembered test commands for the current repository, test selection and environment.", [
        E("eq", "$repository", "@repository"), E("eq", "$test_selector", "@selector"), E("eq", "$environment", "@environment"),
        E("eq", "$last_exit_code", 0)], {"repository": ["ledger", "atlas", "beacon"], "selector": ["unit", "parser", "integration"], "environment": ["py311", "py312", "node22"]})
    add("shell_history", "quoted_filename", "Select a history entry that passes the complete filename as one argument without shell expansion.", [
        E("eq", "$parsed_path", "@path"), E("eq", "$path_argument_count", 1), E("eq", "$shell_expansion_present", False),
        E("eq", "$operation", "inspect")], {"path": ["draft notes.txt", "report[final].csv", "cost$estimate.txt"]})
    add("shell_history", "search_scope", "Pick an offline search command with the requested literal, suffix and directory scope.", [
        E("eq", "$literal_pattern", "@pattern"), E("eq", "$fixed_strings", True), E("eq", "$file_suffix", "@suffix"),
        E("eq", "$root_directory", "src")], {"pattern": ["a+b", "item.name", "[DONE]"], "suffix": ["py", "ts", "rs"]})
    add("shell_history", "git_history_query", "Rank nonmutating Git history queries by exact branch and requested object type.", [
        E("eq", "$revision", "@revision"), E("in", "$subcommand", ["log", "show"]), E("eq", "$modifies_checkout", False),
        E("eq", "$requested_object", "@object")], {"revision": ["main", "release", "experiment"], "object": ["commit", "file", "tag"]})
    add("shell_history", "archive_extract", "Choose a remembered extraction command with an existing destination and no traversal member.", [
        E("eq", "$archive_format", "@format"), E("eq", "$destination_exists", True), E("eq", "$contains_parent_traversal", False),
        E("eq", "$overwrite_existing", False)], {"format": ["tar", "zip", "tar_gzip"]})
    add("shell_history", "dependency_install", "Select an installation history entry that respects the active environment and frozen lockfile.", [
        E("eq", "$environment_path", "@environment_path"), E("eq", "$lockfile_digest", "@lockfile"),
        E("eq", "$updates_lockfile", False), E("eq", "$uses_system_environment", False)], {"environment_path": [".venv", "env_dev", "env_test"], "lockfile": ["lock_A", "lock_B", "lock_C"]})
    add("shell_history", "port_inspection", "Choose a port-inspection command for the requested protocol and endpoint without killing its owner.", [
        E("eq", "$port", "@port"), E("eq", "$protocol", "@protocol"), E("eq", "$listening_only", True),
        E("eq", "$signals_processes", False)], {"port": [8080, 8791, 9000], "protocol": ["tcp", "udp"]})
    add("shell_history", "checksum_verify", "Pick a checksum verification entry that uses the specified algorithm and checks the exact file.", [
        E("eq", "$algorithm", "sha256"), E("eq", "$target_file", "@file"), E("eq", "$expected_digest_source", "trusted_manifest"),
        E("eq", "$comparison_performed", True)], {"file": ["weights.bin", "data.jsonl", "archive.tar"]})
    add("shell_history", "incremental_copy", "Select an incremental copy command whose exclusions and source/destination direction match the request.", [
        E("eq", "$source_directory", "@source"), E("eq", "$destination_directory", "@destination"), E("has", "$excluded_paths", ".git"),
        E("and", E("has", "$excluded_paths", ".env"), E("eq", "$delete_destination_extras", False))], {"source": ["work", "build", "staging"], "destination": ["backup", "mirror", "snapshot"]})
    add("shell_history", "log_time_window", "Rank log queries by service and exact inclusive-start/exclusive-end time bounds.", [
        E("eq", "$service", "@service"), E("eq", "$start_time", "@start"), E("eq", "$end_time", "@end"),
        E("and", E("eq", "$start_inclusive", True), E("eq", "$end_exclusive", True))], {"service": ["worker", "gateway", "scheduler"], "start": [10, 20, 30], "end": [40, 50, 60]})

    # Abstract game plans, not claimed UT99/racing simulator episodes.
    add("games", "safe_path", "Choose a grid-navigation plan that reaches the goal without revisiting a blocked cell and within the move budget.", [
        E("eq", "$end_cell", "@goal"), E("eq", "$blocked_cells_crossed", 0), E("le", "$moves", "@move_budget"),
        E("eq", "$path_is_connected", True)], {"goal": [7, 15, 23], "move_budget": [8, 12, 20]})
    add("games", "projectile_dodge", "Select a dodge plan arriving outside the blast radius before impact without crossing a wall.", [
        E("gt", "$distance_from_impact", "$blast_radius"), E("lt", "$arrival_tick", "$impact_tick"),
        E("eq", "$wall_crossings", 0), E("le", "$stamina_cost", "$stamina_available")])
    add("games", "weapon_selection", "Choose a weapon plan with enough ammunition, valid range and no friendly unit in its firing lane.", [
        E("ge", "$loaded_ammo", "$shots_required"), E("ge", "$effective_range", "$target_distance"),
        E("eq", "$friendly_in_lane", False), E("ge", E("mul", "$damage_per_shot", "$shots_required"), "$target_health")])
    add("games", "reload_cover", "Choose a reload action that completes before exposure and preserves a reachable escape route.", [
        E("le", "$reload_ticks", "$cover_remaining_ticks"), E("gt", "$reserve_ammo", 0),
        E("eq", "$escape_route_clear", True), E("not", E("and", E("eq", "$cover_flammable", True), E("eq", "$fire_nearby", True)))])
    add("games", "health_pickup", "Select a healing detour that can be survived and produces a positive net health gain.", [
        E("lt", "$incoming_damage", "$current_health"), E("gt", "$healing_amount", "$incoming_damage"),
        E("eq", "$pickup_present", True), E("le", "$detour_ticks", "@deadline")], {"deadline": [10, 20, 30]})
    add("games", "escort_sync", "Choose an escort movement that keeps both units in range and reaches cover before the threat.", [
        E("le", "$separation", "@escort_radius"), E("lt", "$cover_arrival_tick", "$threat_arrival_tick"),
        E("eq", "$escort_alive", True), E("eq", "$destination_supports_two_units", True)], {"escort_radius": [3, 5, 8]})
    add("games", "racing_braking", "Choose a braking plan that reaches the corner below its speed limit without a rear collision.", [
        E("le", "$corner_speed", "$corner_speed_limit"), E("le", "$braking_distance", "$distance_to_corner"),
        E("ge", "$following_gap", "$minimum_safe_gap"), E("eq", "$traction_control_fault", False)])
    add("games", "racing_overtake", "Select an overtake plan with enough straight-line distance, clearance and an unblocked return lane.", [
        E("ge", "$straight_remaining", "$passing_distance"), E("gt", "$relative_speed", 0),
        E("eq", "$return_lane_clear", True), E("implies", E("eq", "$yellow_flag", True), E("eq", "$overtake_cancelled", True))])
    add("games", "pit_stop", "Select a pit plan that covers remaining fuel demand and respects the mandatory service window.", [
        E("ge", E("add", "$fuel_remaining", "$fuel_added"), "$fuel_needed"), E("ge", "$pit_lap", "@window_start"),
        E("le", "$pit_lap", "@window_end"), E("eq", "$required_tire_change", True)], {"window_start": [3, 5, 7], "window_end": [10, 12, 14]})
    add("games", "crafting_dependencies", "Choose a crafting plan with enough two-stage ingredients and a tool that survives the operation.", [
        E("ge", "$raw_units", E("mul", "$intermediate_units", "$raw_per_intermediate")), E("ge", "$intermediate_units", "$final_units"),
        E("ge", "$tool_durability", "$durability_cost"), E("has", "$unlocked_recipes", "final_recipe")])

    # Explicit, human-readable finite judging rubrics; no claim of human preference labels.
    add("rubric_judge", "faithful_summary", "Judge a summary under an explicit factual coverage and non-invention rubric.", [
        E("has", "$covered_facts", "main_event"), E("has", "$covered_facts", "outcome"), E("eq", "$invented_facts", 0),
        E("le", "$summary_words", "@word_limit")], {"word_limit": [30, 50, 80]})
    add("rubric_judge", "negation_preservation", "Judge whether an answer preserves a source negation, its quantifier and the relevant subject.", [
        E("eq", "$answer_negated", "$source_negated"), E("eq", "$answer_quantifier", "$source_quantifier"),
        E("eq", "$answer_subject", "$source_subject"), E("eq", "$double_negation_unresolved", False)])
    add("rubric_judge", "format_and_content", "Choose an answer meeting both the required schema and factual content, not just a valid-looking format.", [
        E("eq", "$schema_valid", True), E("has", "$present_fields", "answer"), E("has", "$present_fields", "evidence"),
        E("and", E("eq", "$answer_supported", True), E("eq", "$extra_fields", 0))])
    add("rubric_judge", "unit_conversion", "Judge an explicit integer unit conversion including the multiplier, output value and output unit.", [
        E("eq", "$output_value", E("mul", "$input_value", "$conversion_multiplier")), E("eq", "$conversion_multiplier", "@multiplier"),
        E("eq", "$output_unit", "@unit"), E("eq", "$unsupported_rounding", False)], {"multiplier": [2, 5, 10], "unit": ["minutes", "centimeters", "cents"]})
    add("rubric_judge", "abstention_quality", "Judge an abstention that names the missing evidence without inventing a definite answer.", [
        E("eq", "$states_insufficient_evidence", True), E("has", "$identified_gaps", "@required_gap"),
        E("eq", "$definite_unsupported_answer", False), E("eq", "$claims_evidence_is_false", False)], {"required_gap": ["date", "identity", "jurisdiction"]})
    add("rubric_judge", "comparison_fairness", "Judge a comparison that reports both sides under the same denominator and excludes unmeasured superiority claims.", [
        E("eq", "$left_denominator", "$right_denominator"), E("eq", "$same_metric_definition", True), E("has", "$reported_sides", "left"),
        E("and", E("has", "$reported_sides", "right"), E("eq", "$unmeasured_superiority_claim", False))])
    add("rubric_judge", "instruction_priority", "Judge compliance with a higher-priority instruction when quoted material contains conflicting demands.", [
        E("eq", "$higher_priority_followed", True), E("eq", "$quoted_instruction_executed", False),
        E("eq", "$required_output_language", "$actual_output_language"), E("eq", "$unrequested_external_action", False)])
    add("rubric_judge", "trace_consistency", "Judge a tool-use explanation whose stated result agrees with the final verified tool state.", [
        E("eq", "$reported_result", "$verified_result"), E("ge", "$verification_sequence", "$action_sequence"),
        E("eq", "$ignored_failure", False), E("implies", E("eq", "$action_pending", True), E("eq", "$claimed_complete", False))])
    add("rubric_judge", "balanced_tradeoff", "Judge a recommendation that covers two required constraints and discloses a material unresolved tradeoff.", [
        E("has", "$addressed_constraints", "cost"), E("has", "$addressed_constraints", "reliability"),
        E("implies", E("eq", "$tradeoff_unresolved", True), E("eq", "$tradeoff_disclosed", True)), E("eq", "$guaranteed_unmeasured_outcome", False)])
    add("rubric_judge", "citation_attribution", "Judge attribution that distinguishes a quoted author's claim from independently measured evidence.", [
        E("eq", "$author_claim_labeled", True), E("eq", "$quoted_score_presented_as_own_measurement", False),
        E("has", "$attribution_fields", "source"), E("implies", E("eq", "$comparison_conditions_differ", True), E("eq", "$conditions_disclosed", True))])
    return result


POLICIES = policies()
BY_NAME = {item["domain"] + "/" + item["name"]: item for item in POLICIES}


def evaluate(expression, facts, parameters):
    """Three-valued explicit evidence: missing values are unknown, never false facts."""
    if isinstance(expression, str):
        if expression.startswith("$"):
            return facts.get(expression[1:])
        if expression.startswith("@"):
            return parameters[expression[1:]]
        return expression
    if not isinstance(expression, tuple):
        return expression
    op, *arguments = expression
    values = [evaluate(value, facts, parameters) for value in arguments]
    if op == "and":
        return False if any(value is False for value in values) else None if None in values else True
    if op == "or":
        return True if any(value is True for value in values) else None if None in values else False
    if op == "not":
        return None if values[0] is None else not values[0]
    if op == "implies":
        return evaluate(E("or", E("not", arguments[0]), arguments[1]), facts, parameters)
    if any(value is None for value in values):
        return None
    a = values[0]
    if op == "abs":
        return abs(a)
    b = values[1]
    operations = {"eq": lambda: a == b, "ne": lambda: a != b, "le": lambda: a <= b,
                  "lt": lambda: a < b, "ge": lambda: a >= b, "gt": lambda: a > b,
                  "add": lambda: a + b, "sub": lambda: a - b, "mul": lambda: a * b,
                  "has": lambda: b in a, "in": lambda: a in b}
    return operations[op]()


def references(expression):
    if isinstance(expression, str) and expression.startswith("$"):
        return {expression[1:]}
    if isinstance(expression, tuple):
        return set().union(*(references(value) for value in expression[1:]))
    return set()


def field_domains(policy, parameters):
    """Build boundary-rich value pools from the authored rules, not gold examples."""
    hints, sets, numeric = defaultdict(list), defaultdict(list), set()
    fields = set().union(*(references(rule) for rule in policy["checks"]))
    equalities = []

    def field(value):
        return value[1:] if isinstance(value, str) and value.startswith("$") else None

    def literal(value):
        return parameters[value[1:]] if isinstance(value, str) and value.startswith("@") else value

    def visit(rule):
        if not isinstance(rule, tuple):
            return
        op, *args = rule
        if op in ("le", "lt", "ge", "gt", "add", "sub", "mul", "abs"):
            numeric.update(references(rule))
        if op in ("eq", "ne") and any(isinstance(x, tuple) for x in args):
            numeric.update(references(rule))
        if len(args) == 2:
            left, right = args
            lf, rf = field(left), field(right)
            if op in ("eq", "ne") and lf and rf:
                equalities.append((lf, rf))
            if op == "has" and lf:
                sets[lf].append(right)
            elif op == "in" and lf:
                hints[lf].extend(right)
            elif op in ("eq", "ne", "le", "lt", "ge", "gt"):
                if lf and not rf and not isinstance(right, tuple):
                    hints[lf].append(literal(right))
                if rf and not lf and not isinstance(left, tuple):
                    hints[rf].append(literal(left))
        for value in args:
            visit(value)

    for rule in policy["checks"]:
        visit(rule)
    for _ in range(len(equalities) + 1):
        for a, b in equalities:
            combined = list(dict.fromkeys(hints[a] + hints[b]))
            hints[a], hints[b] = combined[:], combined[:]
            if a in numeric or b in numeric:
                numeric.update((a, b))
    pools = {}
    for name in sorted(fields - sets.keys()):
        values = hints[name]
        if values and all(type(value) is bool for value in values):
            pools[name] = [False, True]
        elif name in numeric or values and all(type(value) is int for value in values):
            numbers = [value for value in values if type(value) is int]
            pools[name] = sorted({0, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, *(
                max(0, value + delta) for value in numbers for delta in (-2, -1, 0, 1, 2, 10))})
        elif values:
            pools[name] = list(dict.fromkeys([*values, "other_value"]))
        elif "unit" in name:
            pools[name] = ["kg", "m", "seconds"]
        elif "negated" in name:
            pools[name] = [False, True]
        elif "quantifier" in name:
            pools[name] = ["all", "some", "none"]
        elif "population" in name:
            pools[name] = ["adults", "adolescents", "older_adults"]
        elif "language" in name:
            pools[name] = ["English", "Japanese", "Korean"]
        else:
            pools[name] = ["record_A", "record_B", "record_C", "record_D"]
    for name, members in sorted(sets.items()):
        values = []
        for member in members:
            values.extend(pools[field(member)] if field(member) else [literal(member)])
        values = list(dict.fromkeys([*values, "unrelated_item"]))
        # At most four relevant symbols in these original specifications.
        if len(values) > 8:
            raise ValueError("Set field has too many independent symbols")
        pools[name] = [list(group) for size in range(len(values) + 1) for group in itertools.combinations(values, size)]
    return pools


def render_rule(expression, parameters):
    if isinstance(expression, str) and expression.startswith("$"):
        return expression[1:]
    if isinstance(expression, str) and expression.startswith("@"):
        return json.dumps(parameters[expression[1:]], ensure_ascii=False)
    if not isinstance(expression, tuple):
        return json.dumps(expression, ensure_ascii=False)
    op, *args = expression
    values = [render_rule(value, parameters) for value in args]
    if op == "not":
        return "NOT (" + values[0] + ")"
    if op == "abs":
        return "absolute value of (" + values[0] + ")"
    if op == "implies":
        return "IF (" + values[0] + ") THEN (" + values[1] + ")"
    signs = {"eq": "equals", "ne": "differs from", "le": "<=", "lt": "<", "ge": ">=", "gt": ">",
             "and": "AND", "or": "OR", "add": "+", "sub": "-", "mul": "times", "has": "contains", "in": "is a member of"}
    return "(" + (" " + signs[op] + " ").join(values) + ")"


def established(policy, facts, parameters):
    return [evaluate(rule, facts, parameters) for rule in policy["checks"]]


def admissible(policy, facts, parameters):
    return all(value is True for value in established(policy, facts, parameters))


def sample_candidate(policy, parameters, pools, rng, wanted):
    for _ in range(20000):
        facts = {name: copy.deepcopy(rng.choice(values)) for name, values in pools.items()}
        if wanted:
            # Construct exact joins and arithmetic equalities rather than relying
            # on rare random collisions (e.g. value = quantity * multiplier).
            # Repetition resolves dependencies between separate requirements.
            for _ in range(len(policy["checks"])):
                for rule in policy["checks"]:
                    if rule[0] == "eq" and isinstance(rule[1], str) and rule[1].startswith("$"):
                        value = evaluate(rule[2], facts, parameters)
                        if value is not None:
                            facts[rule[1][1:]] = copy.deepcopy(value)
        truth = established(policy, facts, parameters)
        if (all(value is True for value in truth) if wanted else sum(value is True for value in truth) <= 2):
            return facts
    raise ValueError("Could not construct candidate for " + policy["domain"] + "/" + policy["name"])


def change_one(policy, parameters, facts, pools, rng, missing=False):
    fields = list(pools)
    rng.shuffle(fields)
    for name in fields:
        values = [None] if missing else copy.deepcopy(pools[name])
        rng.shuffle(values)
        if not missing and type(facts[name]) is int:
            values.extend(value for value in (facts[name] - 1, facts[name] + 1) if value >= 0)
            values.sort(key=lambda value: abs(value - facts[name]))
        elif not missing and isinstance(facts[name], list):
            values.sort(key=lambda value: len(set(value).symmetric_difference(facts[name])))
        for value in values:
            if value == facts[name]:
                continue
            candidate = copy.deepcopy(facts)
            candidate[name] = value
            if not admissible(policy, candidate, parameters):
                return candidate, name
    raise ValueError("No single-fact counterfactual for " + policy["name"])


LANGUAGE_TEXT = {
    "en": {"choice": "Which candidate is supported by all four requirements? Apply the stated tie-break; abstain if none is fully supported.",
           "noul": "Is this candidate supported by all four requirements? Unknown evidence does not establish eligibility.",
           "score": "How many of the four requirements are established for this candidate? Count each numbered requirement once; unknown is not established."},
    "en+zh": {"choice": "哪个候选方案有证据满足全部四项要求？按给定规则打破平局；没有完全满足的候选项时选择 abstain。",
              "noul": "证据是否足以确认该候选方案满足全部四项要求？未知信息不能视为已满足。",
              "score": "该候选方案有多少项要求得到证据支持？四个编号要求各计一次；未知信息不计为满足。"},
    "en+ja": {"choice": "4つの要件すべてを満たす根拠がある候補はどれですか。同点時の規則を適用し、該当する候補がなければ abstain を選んでください。",
              "noul": "この候補が4つの要件すべてを満たすことは、証拠から確認できますか。不明な情報は要件を満たす証拠ではありません。",
              "score": "この候補について、証拠により確認できる要件はいくつありますか。番号付きの4要件を各1回数え、不明なものは数えないでください。"},
    "en+ko": {"choice": "네 가지 요건을 모두 충족한다는 근거가 있는 후보는 무엇인가요? 명시된 동점 처리 규칙을 적용하고 해당 후보가 없으면 abstain을 선택하세요.",
              "noul": "이 후보가 네 가지 요건을 모두 충족한다는 근거가 있나요? 알 수 없는 정보는 충족 근거가 아닙니다.",
              "score": "이 후보에서 근거로 확인되는 요건은 몇 개인가요? 번호가 붙은 네 요건을 각각 한 번 세고 알 수 없는 것은 세지 마세요."},
}
EVIDENCE_POLICY = ("Each numbered requirement must be established by the visible candidate facts. null means unreported, not false. "
                   "AND is false if any operand is false, otherwise unknown if any operand is unknown; OR is true if any operand is true, "
                   "otherwise unknown if any operand is unknown. NOT unknown is unknown. IF A THEN B means (NOT A) OR B. "
                   "A comparison or arithmetic expression with an unreported operand is unknown. Nested clauses form one numbered requirement.")


def candidates_from_state(state):
    raw = state["candidates"]
    if isinstance(raw, list):
        return {item["candidate"]: item["facts"] for item in raw}
    if isinstance(raw, dict):
        return raw
    return {label: json.loads(facts) for label, facts in (line.split("\t", 1) for line in raw.splitlines())}


def oracle(state):
    policy = BY_NAME[state["policy_name"]]
    parameters = state["request_parameters"]
    expected_rules = [render_rule(rule, parameters) for rule in policy["checks"]]
    if state["numbered_requirements"] != expected_rules or state["evidence_policy"] != EVIDENCE_POLICY:
        raise ValueError("Visible policy does not match its declared rule specification")
    facts = candidates_from_state(state)
    truth = {label: established(policy, values, parameters) for label, values in facts.items()}
    eligible = [label for label, values in truth.items() if all(value is True for value in values)]
    rank, direction = policy["rank"]
    expected_selection = f"Among fully supported candidates choose the {'smallest' if direction == 'min' else 'largest'} {rank}; if tied choose the lexicographically smallest candidate ID. If none is fully supported choose abstain."
    if state["selection_rule"] != expected_selection:
        raise ValueError("Visible selection rule differs")
    winner = min(eligible, key=lambda label: (facts[label][rank] * (1 if direction == "min" else -1), label)) if eligible else "abstain"
    return winner, truth


def expected_target(row):
    winner, truth = oracle(row["state"])
    if row["kind"] == "choice":
        answer = winner
    else:
        prefix, separator, _ = row["question"].partition(". ")
        if not separator or not prefix.startswith("Candidate "):
            raise ValueError("Question must identify its evidence candidate")
        probe = prefix.removeprefix("Candidate ")
        values = truth[probe]
        if row["kind"] == "noul":
            answer = "yes" if all(value is True for value in values) else "no"
        else:
            answer = f"Exactly {sum(value is True for value in values)} of the 4 numbered requirements are established."
    if answer not in row["options"]:
        raise ValueError("Oracle answer is absent from candidates")
    return [float(option == answer) for option in row["options"]]


def make_contexts(policy, index, seed, nonce=0):
    key = policy["domain"] + "/" + policy["name"]
    rng = random.Random(_hash([VERSION, seed, key, index, nonce]))
    parameters = {name: rng.choice(values) for name, values in policy["parameters"].items()}
    pools = field_domains(policy, parameters)
    first = sample_candidate(policy, parameters, pools, rng, True)
    second = sample_candidate(policy, parameters, pools, rng, True)
    third_valid = sample_candidate(policy, parameters, pools, rng, True)
    third, repair_field = change_one(policy, parameters, third_valid, pools, rng)
    fourth = sample_candidate(policy, parameters, pools, rng, False)
    fifth, _ = change_one(policy, parameters, second, pools, rng, missing=True)
    values = [first, second, third, fourth, fifth]
    values.extend(sample_candidate(policy, parameters, pools, rng, False) for _ in range(rng.randrange(3)))
    rank, direction = policy["rank"]
    base_rank = rng.randint(20, 100)
    # Candidate 3 has a better tie-break but one disqualifying fact.
    offsets = [2, 4, 1, 6, 8, 10, 12]
    for item, offset in zip(values, offsets):
        item[rank] = base_rank + offset * (1 if direction == "min" else -1)
    third_valid[rank] = third[rank]
    first_bad, break_field = change_one(policy, parameters, first, pools, rng)
    second_unknown, missing_field = change_one(policy, parameters, second, pools, rng, missing=True)
    labels = rng.sample([f"{prefix}{number}" for prefix in ("P", "item_", "K") for number in range(10, 99)], len(values))
    variants = [copy.deepcopy(values) for _ in range(4)]
    variants[1][0] = first_bad
    variants[2][2] = third_valid
    variants[3] = copy.deepcopy(variants[1])
    variants[3][1] = second_unknown
    changes = [None, {"parent_variant": 0, "candidate": labels[0], "field": break_field},
               {"parent_variant": 0, "candidate": labels[2], "field": repair_field},
               {"parent_variant": 1, "candidate": labels[1], "field": missing_field}]
    order = list(range(len(labels)))
    rng.shuffle(order)
    style = index % 3
    contexts = []
    for variant, facts in enumerate(variants):
        ordered = {labels[position]: facts[position] for position in order}
        rendered = ([{"candidate": label, "facts": item} for label, item in ordered.items()] if style == 0 else
                    ordered if style == 1 else "\n".join(label + "\t" + json.dumps(item, ensure_ascii=False, sort_keys=True) for label, item in ordered.items()))
        state = {"policy_name": key, "scenario": policy["setting"], "request_parameters": parameters,
                 "numbered_requirements": [render_rule(rule, parameters) for rule in policy["checks"]],
                 "evidence_policy": EVIDENCE_POLICY,
                 "selection_rule": f"Among fully supported candidates choose the {'smallest' if direction == 'min' else 'largest'} {rank}; if tied choose the lexicographically smallest candidate ID. If none is fully supported choose abstain.",
                 "candidates": rendered}
        expected = [labels[0], labels[1], labels[2], "abstain"][variant]
        if oracle(state)[0] != expected:
            raise ValueError("Counterfactual construction did not change the decision as intended")
        # Ignore names, ordering, serialization and a uniform rank offset.
        # Moving every quoted cost by the same amount does not make a new decision.
        rank_floor = min(item[rank] for item in facts)
        normalized = [{**item, rank: item[rank] - rank_floor} for item in facts]
        semantic_hash = _hash([key, parameters, sorted(normalized, key=_hash)])
        contexts.append((state, changes[variant], semantic_hash))
    return contexts


def generate(groups_per_family=80, seed=20260921):
    if type(groups_per_family) is not int or groups_per_family < 1 or groups_per_family > 1000:
        raise ValueError("groups_per_family must be an integer between 1 and 1000")
    seen, domain_positions = set(), Counter()
    for policy in POLICIES:
        domain = policy["domain"]
        position = domain_positions[domain]
        domain_positions[domain] += 1
        split = ("train",) * 6 + ("calibration", "validation", "test", "ood")
        split = split[position]
        key = domain + "/" + policy["name"]
        for index in range(groups_per_family):
            group = f"{VERSION}/{seed}/{key}/{index}"
            language = list(LANGUAGE_TEXT)[index % 4] if domain == "support" else "en"
            for nonce in range(1000):
                contexts = make_contexts(policy, index, seed, nonce)
                hashes = [item[2] for item in contexts]
                if len(set(hashes)) == 4 and not set(hashes) & seen:
                    break
            else:
                raise ValueError("Could not construct a semantically new scenario")
            for variant, (state, change, semantic_hash) in enumerate(contexts):
                if semantic_hash in seen:
                    raise ValueError("A context differs only in candidate names/order/serialization")
                seen.add(semantic_hash)
                rng = random.Random(_hash([group, variant, "questions"]))
                facts = candidates_from_state(state)
                _, truths = oracle(state)
                ranked = sorted(facts, key=lambda label: (sum(value is True for value in truths[label]), label))
                probe = ranked[(index + variant) % len(ranked)]
                for kind in ("choice", "noul" if (index + variant) % 2 == 0 else "score"):
                    options = list(facts) + ["abstain"] if kind == "choice" else ["no", "yes"] if kind == "noul" else [
                        f"Exactly {number} of the 4 numbered requirements are established." for number in range(5)]
                    if kind == "choice":
                        rng.shuffle(options)
                    question = LANGUAGE_TEXT[language][kind]
                    if kind != "choice":
                        question = f"Candidate {probe}. " + question
                    metadata = {"family": {"support": "policy", "ir": "evidence", "contracts": "policy", "rag": "evidence",
                        "browser_tools": "routing", "shell_history": "routing", "games": "policy", "rubric_judge": "rubric"}[domain],
                        "domain": domain, "scenario_family": key, "template_id": VERSION + "/" + key,
                        "language": language, "source_instance_id": group, "semantic_context_sha256": semantic_hash,
                        "counterfactual": change, "target_basis": "three_valued_visible_rules_exact_one_hot",
                        "provenance": {"type": "synthetic", "generator_version": VERSION, "seed": seed,
                            "group_index": index, "construction_nonce": nonce, "variant": variant, "license": "CC0-1.0", "split_policy": SPLIT_POLICY,
                            "inspiration_urls": SOURCES[domain], "source_examples_imported": False}}
                    if kind == "score":
                        metadata["score_values"] = list(range(5))
                    row = {"id": f"{group}/{variant}/{kind}", "group_id": group, "split": split,
                           "source": VERSION + "/" + key, "state": state, "question": question,
                           "kind": kind, "options": options, "target": [], "metadata": metadata}
                    row["target"] = expected_target(row)
                    yield row


def audit_records(rows):
    summary = validate_records(rows)
    sources, families, instances, contexts = {}, {}, {}, {}
    kinds_by_domain = defaultdict(Counter)
    for row in rows:
        if row["target"] != expected_target(row):
            raise ValueError("Target does not follow the visible original rules")
        metadata = row["metadata"]
        for registry, name in ((sources, row["source"]), (families, metadata["scenario_family"]),
                               (instances, metadata["source_instance_id"]), (contexts, metadata["semantic_context_sha256"])):
            if name in registry and registry[name] != row["split"]:
                raise ValueError("Source/family/context crosses dataset splits")
            registry[name] = row["split"]
        kinds_by_domain[metadata["domain"]][row["kind"]] += 1
    choice_rows = [row for row in rows if row["kind"] == "choice"]
    if len(contexts) != len(choice_rows):
        raise ValueError("Repeated semantic contexts disguised by labels or presentation")
    groups = defaultdict(dict)
    for row in choice_rows:
        groups[row["group_id"]][row["metadata"]["provenance"]["variant"]] = row
    for variants in groups.values():
        if set(variants) != set(range(4)) or len({oracle(row["state"])[0] for row in variants.values()}) != 4:
            raise ValueError("A scenario must contain four distinct counterfactual decisions")
        for variant in (1, 2, 3):
            change = variants[variant]["metadata"]["counterfactual"]
            before = candidates_from_state(variants[change["parent_variant"]]["state"])
            after = candidates_from_state(variants[variant]["state"])
            changed = [(label, field) for label in before for field in before[label] if before[label][field] != after[label][field]]
            if changed != [(change["candidate"], change["field"])]:
                raise ValueError("Counterfactual must change exactly the declared visible fact")
    return {"summary": summary, "domain_counts": dict(Counter(row["metadata"]["domain"] for row in rows)),
            "language_counts": dict(Counter(row["metadata"]["language"] for row in rows)),
            "scenario_family_count": len(families), "generator_source_identifier_count": len(sources),
            "external_inspiration_url_count": len(set(url for values in SOURCES.values() for url in values)),
            "original_source_instance_count": len(instances), "unique_semantic_contexts": len(contexts),
            "single_fact_counterfactual_pairs": len(groups) * 3,
            "candidate_count_distribution": dict(sorted(Counter(len(row["options"]) for row in choice_rows).items())),
            "choice_target_position_counts": dict(sorted(Counter(row["target"].index(1.) for row in choice_rows).items())),
            "noul_target_counts": dict(Counter(row["options"][row["target"].index(1.)] for row in rows if row["kind"] == "noul")),
            "score_target_counts": dict(sorted(Counter(row["target"].index(1.) for row in rows if row["kind"] == "score").items())),
            "abstention_choice_count": sum(row["options"][row["target"].index(1.)] == "abstain" for row in choice_rows),
            "task_kinds_by_domain": {key: dict(value) for key, value in kinds_by_domain.items()},
            "checks": {"all_targets_recomputed_from_visible_rules": True, "family_disjoint_splits": True,
                       "generator_source_disjoint_splits": True, "source_instance_disjoint_splits": True,
                       "semantic_context_disjoint_splits": True, "no_candidate_renaming_duplicates": True,
                       "all_counterfactual_edges_change_exactly_one_fact": True}}


def build_dataset(output_dir, groups_per_family=80, seed=20260921):
    output = Path(output_dir)
    if output.is_symlink() or output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("Choose a new empty output directory")
    rows = list(generate(groups_per_family, seed))
    audit = audit_records(rows)
    configuration = {"type": "synthetic", "generator_version": VERSION, "seed": seed,
        "groups_per_family": groups_per_family, "split_policy": SPLIT_POLICY, "license": "CC0-1.0",
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "benchmark_inputs_read": False, "external_examples_imported": False, "paid_calls": 0,
        "inspiration_sources": SOURCES}
    manifest = _write_dataset(rows, output, configuration)
    manifest.update(audit)
    manifest["authored_families"] = [{"domain": p["domain"], "name": p["name"], "setting": p["setting"],
                                     "rules_sha256": _hash(p["checks"])} for p in POLICIES]
    manifest["scope"] = ("Original finite decision-control scenarios inspired by community use-case categories. "
        "80 authored policy families share an explicit rule engine. They are not 80 independently collected external sources. "
        "51,200 records at the default size comprise two task views over 25,600 contexts from 6,400 source scenarios; related variants are correlated.")
    manifest["limitations"] = ["No improvement on JevBench or another benchmark is established by generating this corpus.",
        "Rules and structured candidate attributes are explicit; this is not a substitute for natural-document semantic annotation.",
        "IR uses constrained relevance/eligibility selection, not measured human relevance or full-ranking gold.",
        "Contract rows are original policy controls, not CUAD examples or official span-extraction annotations.",
        "Game rows are abstract plan constraints, not UT99/racing trajectories or closed-loop success evidence.",
        "Support language variants use Chinese/Japanese/Korean questions with English rules and attribute names; they are mixed-language controls without independent linguistic review.",
        "Judge labels follow explicit finite rubrics, not independently collected human preference labels.",
        "Family-heldout splits test new authored specifications within a shared construction grammar; they do not establish arbitrary real-world transfer."]
    manifest.update(training_performed=False, model_inference_performed=False)
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--groups-per-family", type=int, default=80)
    parser.add_argument("--seed", type=int, default=20260921)
    args = parser.parse_args()
    manifest = build_dataset(args.output_dir, args.groups_per_family, args.seed)
    print(json.dumps({key: manifest[key] for key in ("summary", "domain_counts", "language_counts", "scenario_family_count", "unique_semantic_contexts")}, indent=2))


if __name__ == "__main__":
    main()
