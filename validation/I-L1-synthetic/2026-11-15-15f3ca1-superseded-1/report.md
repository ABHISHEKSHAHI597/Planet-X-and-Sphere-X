# I-L1-synthetic — PASS (L1)

Role I L0 + L1 suites (176 tests; assumptions in each test's docstring and in
backend/tests/synthetic/scene.py). Gate-relevant results:
- G2 stack flux unbiasedness: passed
- G4a synthetic (static < 3σ, both S/N): passed, passed
- G4a synthetic (dipole): passed
- G4a naive method fails: passed
- resampling trap teeth: passed
- G0 generator traps: passed

L1 establishes that the algorithms recover the truth *when the world matches the scene's assumptions*;
it never raises a capability above `synthetic` (workflow.md §4.2).

## Metrics

| metric | value | threshold | pass |
|---|---|---|---|
| test_joint_astrometry::test_joint_native_centroid_with_colour_rotation_and_registration_noise | passed | pass | True |
| test_joint_astrometry::test_low_snr_joint_centroid_empirical_uncertainty_coverage | passed | pass | True |
| test_lightcurve_covariance::test_reference_smoothing_and_correlated_errors_against_noise_trials | passed | pass | True |
| test_lightcurve_covariance::test_annulus_does_not_smooth_channels_and_rejects_uncertain_reference | passed | pass | True |
| test_lightcurve_covariance::test_correlated_period_search_and_singular_reference_null | passed | pass | True |
| test_lightcurve_covariance::test_correlated_null_false_alarm_rates_and_invalid_covariance | passed | pass | True |
| test_planetx_recovery::test_orphan_queue_excludes_static_and_known_detections_without_fake_matches | passed | pass | True |
| test_planetx_recovery::test_digital_tracking_recovers_native_injected_source_and_variance | passed | pass | True |
| test_planetx_recovery::test_ambiguous_daily_orphans_do_not_greedily_discard_true_recovery | passed | pass | True |
| test_synthetic_diff::test_synthetic_matched_difference_static_stars_cancel | passed | pass | True |
| test_synthetic_diff::test_synthetic_naive_stack_difference_fails | passed | pass | True |
| test_synthetic_diff::test_synthetic_pairing_at_target_fails_off_centre | passed | pass | True |
| test_synthetic_diff::test_synthetic_mover_leaves_dipole | passed | pass | True |
| test_synthetic_diff::test_synthetic_pair_frames_half_channel_offsets_pair | passed | pass | True |
| test_synthetic_measurement::test_synthetic_300_edge_phase_fits | passed | pass | True |
| test_synthetic_measurement::test_synthetic_blend_naive_bias_and_covariance | passed | pass | True |
| test_synthetic_measurement::test_plane_background_fitting_keeps_native_flux_and_covariance | passed | pass | True |
| test_synthetic_measurement::test_synthetic_pm_fixed_parallax_and_shared_errors | passed | pass | True |
| test_synthetic_measurement::test_synthetic_registration_rejects_outlier | passed | pass | True |
| test_synthetic_measurement::test_parallax_sign_independent_vector | passed | pass | True |
| test_synthetic_photmatch::test_cross_release_difference_is_matched_and_static_stars_cancel | passed | pass | True |
| test_synthetic_photmatch::test_wavelength_dependent_gain_is_followed_per_bin | passed | pass | True |
| test_synthetic_photmatch::test_variable_star_and_mover_do_not_bias_the_scale | passed | pass | True |
| test_synthetic_photmatch::test_same_release_reports_a_diagnostic_and_applies_nothing | passed | pass | True |
| test_synthetic_photmatch::test_sparse_cross_release_field_is_refused_with_a_reason | passed | pass | True |
| test_synthetic_photmatch::test_bootstrap_errors_are_calibrated | passed | pass | True |
| test_synthetic_photmatch::test_breakdown_against_outlier_sources | passed | pass | True |
| test_synthetic_pipeline::test_synthetic_native_matched_difference_static_stars_cancel[25.0] | passed | pass | True |
| test_synthetic_pipeline::test_synthetic_native_matched_difference_static_stars_cancel[400.0] | passed | pass | True |
| test_synthetic_pipeline::test_synthetic_resampling_trap_teeth | passed | pass | True |
| test_synthetic_pipeline::test_synthetic_native_naive_stack_difference_fails | passed | pass | True |
| test_synthetic_pipeline::test_synthetic_native_mover_dipole_and_template_shift | passed | pass | True |
| test_synthetic_pipeline::test_synthetic_native_variable_monopole | passed | pass | True |
| test_synthetic_pipeline::test_synthetic_stack_unbiased_through_pipeline | passed | pass | True |
| test_synthetic_pipeline::test_synthetic_registration_offsets_between_pa_flipped_visits | passed | pass | True |
| test_synthetic_pipeline::test_synthetic_bright_target_presets_fill_and_masked_core_shift | passed | pass | True |
| test_synthetic_pipeline::test_synthetic_null_test_and_occupancy | passed | pass | True |
| test_synthetic_pipeline::test_synthetic_partial_visit_trap | passed | pass | True |
| test_synthetic_pipeline::test_synthetic_qr2_scale_guard | passed | pass | True |
| test_synthetic_pipeline::test_synthetic_detection_native_only_and_transients | passed | pass | True |
| test_synthetic_pipeline::test_synthetic_qa_rejects_and_lists_skipped | passed | pass | True |
| test_synthetic_pipeline::test_synthetic_generator_produces_the_traps | passed | pass | True |
| test_synthetic_pipeline::test_synthetic_difference_refuses_mixed_photometric_scales | passed | pass | True |
| test_synthetic_pipeline::test_synthetic_smooth_background_for_large_boxes | passed | pass | True |
| test_synthetic_stack::test_synthetic_reject_transients_moving_point_on_dark_sky | passed | pass | True |
| test_synthetic_stack::test_synthetic_reject_transients_keeps_skewed_bright_source | passed | pass | True |
| test_synthetic_stack::test_synthetic_weighted_stack_unbiased_bright_star | passed | pass | True |
| test_synthetic_stack::test_synthetic_cosmic_rays_rejected_on_sky | passed | pass | True |
| test_synthetic_stack::test_synthetic_significance_unit_sigma_native_and_upsampled | passed | pass | True |
| test_synthetic_stack::test_synthetic_to_grid_undoes_pa180_rotation | passed | pass | True |
| test_synthetic_stack::test_synthetic_detect_recovers_injected_source_only | passed | pass | True |
| test_synthetic_stack::test_synthetic_red_sum_catches_cold_dwarf | passed | pass | True |
| test_access_fits_sources::test_data_bytes_is_fits_standard | passed | pass | True |
| test_access_fits_sources::test_decode_keeps_integers_and_applies_bzero | passed | pass | True |
| test_access_fits_sources::test_stream_parse_matches_astropy_and_stops_before_epsf | passed | pass | True |
| test_access_fits_sources::test_truncated_stream_raises_eof_and_html_raises_corrupt | passed | pass | True |
| test_access_fits_sources::test_cutout_source_retries_truncation_and_503_then_succeeds | passed | pass | True |
| test_access_fits_sources::test_cutout_source_4xx_is_unavailable_and_exhaustion_is_source_failure | passed | pass | True |
| test_access_fits_sources::test_shift_wcs_header_keeps_world_coordinates_and_origin_rule | passed | pass | True |
| test_access_fits_sources::test_cutout_size_and_snapping | passed | pass | True |
| test_access_fits_sources::test_s3_section_reads_rows_and_compressed_flags | passed | pass | True |
| test_access_fits_sources::test_range_reader_refuses_ignored_range_and_short_body | passed | pass | True |
| test_access_fits_sources::test_irsa_bounds_rule_reproduces_the_fixture_cutout_box | passed | pass | True |
| test_access_fits_sources::test_decode_hdu_handles_compressed_table_whole | passed | pass | True |
| test_access_fits_sources::test_fixture_hash_is_the_committed_one | passed | pass | True |
| test_access_policy::test_registry_loads_and_ranks | passed | pass | True |
| test_access_policy::test_registry_rejects_bad_configs[<lambda>0] | passed | pass | True |
| test_access_policy::test_registry_rejects_bad_configs[<lambda>1] | passed | pass | True |
| test_access_policy::test_registry_rejects_bad_configs[<lambda>2] | passed | pass | True |
| test_access_policy::test_registry_rejects_bad_configs[<lambda>3] | passed | pass | True |
| test_access_policy::test_registry_rejects_bad_configs[<lambda>4] | passed | pass | True |
| test_access_policy::test_filename_parse_retry_and_psffix | passed | pass | True |
| test_access_policy::test_dedup_policy | passed | pass | True |
| test_access_policy::test_dedup_order_independent_and_sorted | passed | pass | True |
| test_access_policy::test_pins_are_order_free_immutable_and_verified | passed | pass | True |
| test_access_policy::test_pin_diff_reports_added_removed_replaced | passed | pass | True |
| test_access_policy::test_coverage_cache_ttl_and_release_state_but_pins_untouched | passed | pass | True |
| test_access_policy::test_failover_after_three_and_reprobe | passed | pass | True |
| test_access_policy::test_failover_ignores_unavailable_and_fetch_frames_reports_skips | passed | pass | True |
| test_access_policy::test_cached_source_hits | passed | pass | True |
| test_access_policy::test_retry_classification_and_giveup | passed | pass | True |
| test_access_policy::test_planning_period_order_and_watcher_never_adopts | passed | pass | True |
| test_access_policy::test_s3_listing_page_parse_and_pagination_token | passed | pass | True |
| test_access_policy::test_watcher_first_run_is_a_baseline | passed | pass | True |
| test_access_policy::test_build_source_defaults_by_region | passed | pass | True |
| test_blink25_grid::test_star_lands_at_its_sky_position_and_epoch_is_on_sky_sigma[1.0-False-True] | passed | pass | True |
| test_blink25_grid::test_star_lands_at_its_sky_position_and_epoch_is_on_sky_sigma[2.75-True-False] | passed | pass | True |
| test_blink25_grid::test_star_lands_at_its_sky_position_and_epoch_is_on_sky_sigma[1.375-False-False] | passed | pass | True |
| test_blink25_grid::test_mosaic_of_images_with_different_zero_points_is_seamless | passed | pass | True |
| test_blink25_grid::test_no_usable_image_is_all_nan_not_zero | passed | pass | True |
| test_blink25_grid::test_read_image_rejects_files_without_celestial_wcs | passed | pass | True |
| test_blink25_grid::test_spherex_epoch_is_on_the_same_sigma_scale | passed | pass | True |
| test_blink25_grid::test_select_epochs_keeps_2mass_allwise_w2_and_thins_neowise | passed | pass | True |
| test_cube_grid_unit::test_at_wavelengths_matches_documented_version_where_it_is_defined | passed | pass | True |
| test_cube_grid_unit::test_shift_pa_convention_and_dipole_fit | passed | pass | True |
| test_cube_grid_unit::test_scrubber_sorted_by_measured_lambda_and_lambda_slice | passed | pass | True |
| test_cube_grid_unit::test_null_halves_disjoint_and_alternate_in_lambda | passed | pass | True |
| test_cube_grid_unit::test_psf_match_variance_of_white_noise | passed | pass | True |
| test_cube_grid_unit::test_grid_helpers | passed | pass | True |
| test_cube_grid_unit::test_bicubic_resampling_is_nan_safe | passed | pass | True |
| test_cube_grid_unit::test_transients_and_empty_stack | passed | pass | True |
| test_deepfield_blink25::test_volume_and_deep_flags | passed | pass | True |
| test_deepfield_blink25::test_cap_frames_is_deterministic_spread_and_reported | passed | pass | True |
| test_deepfield_blink25::test_frame_inputs_on_a_real_full_file_header | passed | pass | True |
| test_deepfield_blink25::test_blink25_helpers | passed | pass | True |
| test_deepfield_blink25::test_blink25_plan_from_recorded_responses | passed | pass | True |
| test_external_clients::test_adql_escaping_and_injection | passed | pass | True |
| test_external_clients::test_simbad_names_and_traps | passed | pass | True |
| test_external_clients::test_gaia_targets_and_cone | passed | pass | True |
| test_external_clients::test_twomass_per_target_epochs_and_non_detection | passed | pass | True |
| test_external_clients::test_wise_sia_and_epoch_grouping | passed | pass | True |
| test_external_clients::test_catwise_finds_wise0855_motion | passed | pass | True |
| test_external_clients::test_skybot_uses_loc_and_parses | passed | pass | True |
| test_external_clients::test_votable_overflow_is_an_error | passed | pass | True |
| test_external_clients::test_allwise_rows_and_query | passed | pass | True |
| test_flags_epochs::test_flag_bits_both_header_conventions | passed | pass | True |
| test_flags_epochs::test_canonical_repack_from_a_different_layout | passed | pass | True |
| test_flags_epochs::test_presets_policy | passed | pass | True |
| test_flags_epochs::test_survey_number_branches | passed | pass | True |
| test_flags_epochs::test_labels_and_date_ranges | passed | pass | True |
| test_flags_epochs::test_time_bins_axes | passed | pass | True |
| test_generalised::test_bright_preset_follows_k_magnitude_for_any_star | passed | pass | True |
| test_generalised::test_red_only_is_any_gaia_invisible_brown_dwarf | passed | pass | True |
| test_generalised::test_blend_neighbours_meets_the_star_a_fast_mover_crosses_now | passed | pass | True |
| test_lite_export::test_file_names_match_the_browser[/views/abc123/manifest-api/views/abc123/manifest.json] | passed | pass | True |
| test_lite_export::test_file_names_match_the_browser[/views/abc123/stack/V1/6.f16-api/views/abc123/stack/V1/6.f16] | passed | pass | True |
| test_lite_export::test_file_names_match_the_browser[/views/abc123/stack/V1/6.f16?raw=1-api/views/abc123/stack/V1/6.f16] | passed | pass | True |
| test_lite_export::test_file_names_match_the_browser[/views/abc123/stack/B2026-01-05%3A14d/3.flags.u32-api/views/abc123/stack/B2026-01-05_14d/3.flags.u32] | passed | pass | True |
| test_lite_export::test_file_names_match_the_browser[/views/abc123/frames?sort=time&band=4-api/views/abc123/frames@band_4_sort_time.json] | passed | pass | True |
| test_lite_export::test_file_names_match_the_browser[/views/abc123/blink25-api/views/abc123/blink25.json] | passed | pass | True |
| test_lite_export::test_file_names_match_the_browser[/views/abc123/blink25/2mass_ks.f16-api/views/abc123/blink25/2mass_ks.f16] | passed | pass | True |
| test_lite_export::test_payload_urls_are_found_at_any_depth | passed | pass | True |
| test_lite_export::test_a_static_copy_never_offers_what_needs_the_server | passed | pass | True |
| test_measurement::test_propagation_catalogue_epoch_and_guard | passed | pass | True |
| test_measurement::test_units_indices_and_scale_guard | passed | pass | True |
| test_measurement::test_lightcurve_channel_mixing_and_region | passed | pass | True |
| test_measurement::test_horizons_csv_and_observer_contract | passed | pass | True |
| test_measurement::test_link_score_vetting_and_rank | passed | pass | True |
| test_pooled_fetch::test_pool_uses_both_sources_within_capacity_and_favours_the_faster | passed | pass | True |
| test_pooled_fetch::test_pool_retries_on_the_other_source_and_rests_a_failing_one | passed | pass | True |
| test_pooled_fetch::test_pool_passes_frame_unavailable_through_without_counting_it | passed | pass | True |
| test_pooled_fetch::test_pool_with_every_source_resting_still_tries_and_reports_the_failure | passed | pass | True |
| test_pooled_fetch::test_served_by_from_inner_source_wins_and_does_not_leak_between_frames | passed | pass | True |
| test_pooled_fetch::test_cached_source_attributes_hits_and_records_the_pool_member | passed | pass | True |
| test_pooled_fetch::test_cached_source_survives_a_failing_cache_write | passed | pass | True |
| test_pooled_fetch::test_frame_cache_contains_matches_get | passed | pass | True |
| test_pooled_fetch::test_s3_outside_aws_warns_once | passed | pass | True |
| test_pooled_fetch::test_canonical_crop_makes_the_window_independent_of_the_source | passed | pass | True |
| test_pooled_fetch::test_canonical_crop_in_place_matches_the_copying_crop | passed | pass | True |
| test_reference::test_original_irsa_export_units_and_frame_provenance | passed | pass | True |
| test_reference::test_independent_comparison_preserves_failures | passed | pass | True |
| test_reference::test_mismatched_data_cannot_satisfy_comparison | passed | pass | True |
| test_render::test_to_f16_sentinel_and_clip | passed | pass | True |
| test_render::test_science_payloads_keep_nan_and_flags_are_u32le | passed | pass | True |
| test_render::test_golden_F_contract_file_and_orientation | passed | pass | True |
| test_render::test_shared_limits_from_median_stack_ignore_one_bright_frame | passed | pass | True |
| test_render::test_per_frame_stretch_flickers_teeth | passed | pass | True |
| test_render::test_stretch_matches_shader_endpoints | passed | pass | True |
| test_render::test_display_fill_only_fills_core_holes | passed | pass | True |
| test_render::test_flipbook_sorted_by_lambda_and_decimated | passed | pass | True |
| test_render::test_normalise_epoch_unit_sky_sigma_and_blink25_plan | passed | pass | True |
| test_sky_noise_scale::test_recovers_the_understatement_factor | passed | pass | True |
| test_sky_noise_scale::test_robust_to_unmasked_sources_and_hot_pixels | passed | pass | True |
| test_sky_noise_scale::test_ignores_star_pixels_entirely | passed | pass | True |
| test_sky_noise_scale::test_too_little_sky_is_nan | passed | pass | True |
| test_visit_centroid::test_visit_mean_retains_covariance_and_does_not_use_arithmetic_weights | passed | pass | True |
| test_visit_centroid::test_two_epoch_motion_uses_known_covariance_without_false_degrees_of_freedom | passed | pass | True |
| test_watcher_calib_replay::test_real_listing_pagination_follows_tokens | passed | pass | True |
| test_watcher_calib_replay::test_discovery_on_real_listings_matches_committed_lock | passed | pass | True |
| test_watcher_calib_replay::test_version_key_and_selection_rules | passed | pass | True |
| test_watcher_calib_replay::test_lock_hash_detects_hand_edits | passed | pass | True |
| test_watcher_calib_replay::test_calib_headers_fixture_matches_lock_and_conventions | passed | pass | True |
| test_watcher_calib_replay::test_bootstrap_verifies_md5_and_sha256 | passed | pass | True |
| test_watcher_calib_replay::test_calib_loader_reads_named_hdus_and_verifies | passed | pass | True |
| test_watcher_calib_replay::test_sliced_calib_supports_parent_slice_lookups | passed | pass | True |
| test_watcher_calib_replay::test_watcher_on_real_listings | passed | pass | True |

## Caveats

- recorded on a dirty working tree: code_digest identifies the exact code

git 15f3ca1 (dirty) · contracts {'spherex.types': '0.1.0', 'http-api': '0.1.0'} · calibration 94e18b883fdc9b28 · author I · reviewer pending
