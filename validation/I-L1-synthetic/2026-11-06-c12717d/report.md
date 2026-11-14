# I-L1-synthetic — PASS (L1)

Role I L0 + L1 suites (52 tests; assumptions in each test's docstring and in
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
| test_synthetic_diff::test_synthetic_matched_difference_static_stars_cancel | passed | pass | True |
| test_synthetic_diff::test_synthetic_naive_stack_difference_fails | passed | pass | True |
| test_synthetic_diff::test_synthetic_pairing_at_target_fails_off_centre | passed | pass | True |
| test_synthetic_diff::test_synthetic_mover_leaves_dipole | passed | pass | True |
| test_synthetic_diff::test_synthetic_pair_frames_half_channel_offsets_pair | passed | pass | True |
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
| test_synthetic_stack::test_synthetic_reject_transients_moving_point_on_dark_sky | passed | pass | True |
| test_synthetic_stack::test_synthetic_reject_transients_keeps_skewed_bright_source | passed | pass | True |
| test_synthetic_stack::test_synthetic_weighted_stack_unbiased_bright_star | passed | pass | True |
| test_synthetic_stack::test_synthetic_cosmic_rays_rejected_on_sky | passed | pass | True |
| test_synthetic_stack::test_synthetic_significance_unit_sigma_native_and_upsampled | passed | pass | True |
| test_synthetic_stack::test_synthetic_to_grid_undoes_pa180_rotation | passed | pass | True |
| test_synthetic_stack::test_synthetic_detect_recovers_injected_source_only | passed | pass | True |
| test_synthetic_stack::test_synthetic_red_sum_catches_cold_dwarf | passed | pass | True |
| test_cube_grid_unit::test_at_wavelengths_matches_documented_version_where_it_is_defined | passed | pass | True |
| test_cube_grid_unit::test_shift_pa_convention_and_dipole_fit | passed | pass | True |
| test_cube_grid_unit::test_scrubber_sorted_by_measured_lambda_and_lambda_slice | passed | pass | True |
| test_cube_grid_unit::test_null_halves_disjoint_and_alternate_in_lambda | passed | pass | True |
| test_cube_grid_unit::test_psf_match_variance_of_white_noise | passed | pass | True |
| test_cube_grid_unit::test_grid_helpers | passed | pass | True |
| test_cube_grid_unit::test_bicubic_resampling_is_nan_safe | passed | pass | True |
| test_cube_grid_unit::test_transients_and_empty_stack | passed | pass | True |
| test_flags_epochs::test_flag_bits_both_header_conventions | passed | pass | True |
| test_flags_epochs::test_canonical_repack_from_a_different_layout | passed | pass | True |
| test_flags_epochs::test_presets_policy | passed | pass | True |
| test_flags_epochs::test_survey_number_branches | passed | pass | True |
| test_flags_epochs::test_labels_and_date_ranges | passed | pass | True |
| test_flags_epochs::test_time_bins_axes | passed | pass | True |
| test_render::test_to_f16_sentinel_and_clip | passed | pass | True |
| test_render::test_science_payloads_keep_nan_and_flags_are_u32le | passed | pass | True |
| test_render::test_golden_F_contract_file_and_orientation | passed | pass | True |
| test_render::test_shared_limits_from_median_stack_ignore_one_bright_frame | passed | pass | True |
| test_render::test_per_frame_stretch_flickers_teeth | passed | pass | True |
| test_render::test_stretch_matches_shader_endpoints | passed | pass | True |
| test_render::test_display_fill_only_fills_core_holes | passed | pass | True |
| test_render::test_flipbook_sorted_by_lambda_and_decimated | passed | pass | True |
| test_render::test_normalise_epoch_unit_sky_sigma_and_blink25_plan | passed | pass | True |

git c12717d (dirty) · contract 0.1.0 · author I · reviewer pending
