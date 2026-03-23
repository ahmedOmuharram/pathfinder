/**
 * AUTO-GENERATED FILE — DO NOT EDIT.
 *
 * Source: packages/spec/openapi.json
 * Generator: packages/shared-ts/scripts/generate-openapi.mjs
 */

export type paths = {
    "/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Health Check
         * @description Liveness check - is the service running?
         */
        get: operations["health_check_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health/config": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * System Config
         * @description Report whether the system has LLM provider keys configured.
         *
         *     This is unauthenticated so the frontend can show a setup-required
         *     screen before asking users to log in.
         */
        get: operations["system_config_health_config_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health/ready": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Readiness Check
         * @description Readiness check - is the service ready to accept requests?
         *
         *     Checks database connectivity.
         *     Returns 503 if any dependency is unreachable.
         */
        get: operations["readiness_check_health_ready_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sites": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Sites
         * @description List all available VEuPathDB sites.
         */
        get: operations["list_sites_api_v1_sites_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sites/{siteId}/record-types": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Record Types
         * @description Get record types available on a site.
         */
        get: operations["get_record_types_api_v1_sites__siteId__record_types_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sites/{siteId}/searches": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Searches
         * @description Get searches available on a site, optionally filtered by record type.
         */
        get: operations["get_searches_api_v1_sites__siteId__searches_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sites/{siteId}/searches/{recordType}/{searchName}/validate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Validate Search Params
         * @description Validate search parameters (UI-friendly).
         */
        post: operations["validate_search_params_api_v1_sites__siteId__searches__recordType___searchName__validate_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sites/{siteId}/searches/{recordType}/{searchName}/param-specs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Get Param Specs With Context
         * @description Return normalized parameter specs, using contextual WDK vocab when provided.
         */
        post: operations["get_param_specs_with_context_api_v1_sites__siteId__searches__recordType___searchName__param_specs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sites/{siteId}/organisms": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Organisms
         * @description Return all available organism names for a site via site-search.
         */
        get: operations["list_organisms_api_v1_sites__siteId__organisms_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sites/{siteId}/genes/search": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Search Genes
         * @description Search genes by text using multi-strategy gene lookup.
         */
        get: operations["search_genes_api_v1_sites__siteId__genes_search_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sites/{siteId}/genes/resolve": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Resolve Genes
         * @description Resolve gene IDs to full records via WDK standard reporter.
         */
        post: operations["resolve_genes_api_v1_sites__siteId__genes_resolve_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/models": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Models
         * @description Return available models grouped by provider.
         *
         *     Models whose provider has no API key are returned with ``enabled: false``
         *     so the frontend can render them as disabled in the picker.
         */
        get: operations["list_models_api_v1_models_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/tools": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Tools
         * @description Return the list of AI tools registered on the agent.
         */
        get: operations["list_tools_api_v1_tools_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/chat": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Chat
         * @description Start a chat operation and return its operation ID.
         *
         *     The client subscribes to GET /operations/{operationId}/subscribe for SSE events.
         */
        post: operations["chat_api_v1_chat_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/strategies": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Strategies
         * @description List user's conversation streams (projections).
         */
        get: operations["list_strategies_api_v1_strategies_get"];
        put?: never;
        /**
         * Create Strategy
         * @description Create a new strategy (CQRS only).
         */
        post: operations["create_strategy_api_v1_strategies_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/strategies/dismissed": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Dismissed Strategies
         * @description List user's dismissed (soft-deleted) strategies.
         */
        get: operations["list_dismissed_strategies_api_v1_strategies_dismissed_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/strategies/{strategyId}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Strategy
         * @description Get a strategy/stream by ID from the CQRS projection + Redis.
         */
        get: operations["get_strategy_api_v1_strategies__strategyId__get"];
        put?: never;
        post?: never;
        /**
         * Delete Strategy
         * @description Delete a strategy: cancel ops, clean Redis stream, delete CQRS records.
         *
         *     For WDK-linked strategies with ``deleteFromWdk=false`` (default), the
         *     strategy is soft-deleted (dismissed) instead of hard-deleted. This prevents
         *     WDK sync from re-importing it. Use the restore endpoint to un-dismiss.
         *
         *     Pass ``deleteFromWdk=true`` to hard-delete from both PathFinder and WDK.
         *     Non-WDK strategies are always hard-deleted.
         */
        delete: operations["delete_strategy_api_v1_strategies__strategyId__delete"];
        options?: never;
        head?: never;
        /**
         * Update Strategy
         * @description Update a strategy (CQRS only).
         */
        patch: operations["update_strategy_api_v1_strategies__strategyId__patch"];
        trace?: never;
    };
    "/api/v1/strategies/{strategyId}/ast": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Strategy Ast
         * @description Return the raw plan AST from a strategy's projection.
         */
        get: operations["get_strategy_ast_api_v1_strategies__strategyId__ast_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/strategies/{strategyId}/restore": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Restore Strategy
         * @description Restore a dismissed (soft-deleted) strategy.
         *
         *     Clears dismissed_at, resets plan to empty (triggers lazy WDK re-fetch),
         *     and wipes message history. The strategy reappears as if freshly imported.
         */
        post: operations["restore_strategy_api_v1_strategies__strategyId__restore_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/strategies/step-counts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Compute Step Counts
         * @description Compute step counts by executing the plan in WDK.
         */
        post: operations["compute_step_counts_api_v1_strategies_step_counts_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/strategies/plan/normalize": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Normalize Plan
         * @description Normalize/coerce plan parameters using backend-owned rules.
         *
         *     This endpoint exists so the frontend can be a consumer of backend canonicalization
         *     (and avoid re-implementing CSV/JSON parsing and WDK quirks).
         */
        post: operations["normalize_plan_api_v1_strategies_plan_normalize_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/strategies/open": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Open Strategy
         * @description Open a strategy by local or WDK strategy.
         */
        post: operations["open_strategy_api_v1_strategies_open_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/strategies/sync-wdk": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Sync All Wdk Strategies
         * @description Batch-sync all WDK strategies into the CQRS layer and return the full list.
         */
        post: operations["sync_all_wdk_strategies_api_v1_strategies_sync_wdk_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/experiments/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Experiments
         * @description List experiments owned by the current user, optionally filtered by site.
         */
        get: operations["list_experiments_api_v1_experiments__get"];
        put?: never;
        /**
         * Create Experiment
         * @description Create and run an experiment as a background task.
         */
        post: operations["create_experiment_api_v1_experiments__post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/experiments/batch": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Create Batch Experiment
         * @description Run the same search across multiple organisms as a background task.
         */
        post: operations["create_batch_experiment_api_v1_experiments_batch_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/experiments/benchmark": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Create Benchmark
         * @description Run the same strategy against multiple control sets as a background task.
         */
        post: operations["create_benchmark_api_v1_experiments_benchmark_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/experiments/seed": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Seed Strategies
         * @description Seed demo strategies and control sets across VEuPathDB sites.
         *
         *     If *site_id* is provided, only seeds for that database are created.
         */
        post: operations["seed_strategies_api_v1_experiments_seed_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/experiments/overlap": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Compute Overlap
         * @description Compute pairwise gene set overlap between experiments.
         */
        post: operations["compute_overlap_api_v1_experiments_overlap_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/experiments/enrichment-compare": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Compare Enrichment
         * @description Compare enrichment results across experiments.
         */
        post: operations["compare_enrichment_api_v1_experiments_enrichment_compare_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/experiments/{experiment_id}/cross-validate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Run Cv
         * @description Run cross-validation on an existing experiment.
         */
        post: operations["run_cv_api_v1_experiments__experiment_id__cross_validate_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/experiments/{experiment_id}/enrich": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Run Enrichment
         * @description Run enrichment analysis on an existing experiment's results.
         */
        post: operations["run_enrichment_api_v1_experiments__experiment_id__enrich_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/experiments/{experiment_id}/custom-enrich": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Custom Enrichment
         * @description Test enrichment of a custom gene set against the experiment results.
         */
        post: operations["custom_enrichment_api_v1_experiments__experiment_id__custom_enrich_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/experiments/{experiment_id}/re-evaluate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Re Evaluate Experiment
         * @description Re-run control evaluation against the (possibly modified) strategy.
         */
        post: operations["re_evaluate_experiment_api_v1_experiments__experiment_id__re_evaluate_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/experiments/{experiment_id}/threshold-sweep": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Threshold Sweep
         * @description Sweep a parameter across a range and stream metrics as they complete.
         */
        post: operations["threshold_sweep_api_v1_experiments__experiment_id__threshold_sweep_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/experiments/{experiment_id}/export": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Experiment Report
         * @description Generate and return a self-contained HTML report for an experiment.
         */
        get: operations["get_experiment_report_api_v1_experiments__experiment_id__export_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/experiments/{experiment_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Experiment
         * @description Get full experiment details including all results.
         */
        get: operations["get_experiment_api_v1_experiments__experiment_id__get"];
        put?: never;
        post?: never;
        /**
         * Delete Experiment
         * @description Delete an experiment and clean up its WDK strategy.
         */
        delete: operations["delete_experiment_api_v1_experiments__experiment_id__delete"];
        options?: never;
        head?: never;
        /**
         * Update Experiment
         * @description Update experiment metadata (e.g. notes).
         */
        patch: operations["update_experiment_api_v1_experiments__experiment_id__patch"];
        trace?: never;
    };
    "/api/v1/experiments/{experiment_id}/results/attributes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Experiment Attributes
         * @description Get available attributes for an experiment's record type.
         */
        get: operations["get_experiment_attributes_api_v1_experiments__experiment_id__results_attributes_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/experiments/{experiment_id}/results/records": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Experiment Records
         * @description Get paginated result records for an experiment.
         *
         *     Requires a persisted WDK strategy (``wdkStepId`` must be set).
         */
        get: operations["get_experiment_records_api_v1_experiments__experiment_id__results_records_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/experiments/{experiment_id}/results/record": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Get Experiment Record Detail
         * @description Get a single record's full details by primary key.
         */
        post: operations["get_experiment_record_detail_api_v1_experiments__experiment_id__results_record_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/experiments/{experiment_id}/results/distributions/{attribute_name}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Experiment Distribution
         * @description Get distribution data for an attribute using the byValue column reporter.
         */
        get: operations["get_experiment_distribution_api_v1_experiments__experiment_id__results_distributions__attribute_name__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/experiments/{experiment_id}/refine": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Refine Experiment
         * @description Add a step to the experiment's strategy (combine, transform, etc.).
         */
        post: operations["refine_experiment_api_v1_experiments__experiment_id__refine_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/experiments/{experiment_id}/chat": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Workbench Chat
         * @description Start a conversational AI chat for an experiment.
         *
         *     Returns operation ID for SSE subscription via
         *     GET /operations/{operationId}/subscribe.
         */
        post: operations["workbench_chat_api_v1_experiments__experiment_id__chat_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/experiments/{experiment_id}/chat/messages": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Workbench Chat Messages
         * @description Get conversation history for an experiment's chat.
         */
        get: operations["get_workbench_chat_messages_api_v1_experiments__experiment_id__chat_messages_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/control-sets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Control Sets
         * @description List control sets visible to the current user.
         */
        get: operations["list_control_sets_api_v1_control_sets_get"];
        put?: never;
        /**
         * Create Control Set
         * @description Create a new control set.
         */
        post: operations["create_control_set_api_v1_control_sets_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/control-sets/{control_set_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Control Set
         * @description Get a single control set by ID.
         */
        get: operations["get_control_set_api_v1_control_sets__control_set_id__get"];
        put?: never;
        post?: never;
        /**
         * Delete Control Set
         * @description Delete a control set owned by the current user.
         */
        delete: operations["delete_control_set_api_v1_control_sets__control_set_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/veupathdb/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Login With Password
         * @description Login via VEuPathDB /login, link internal user, and store auth cookies.
         */
        post: operations["login_with_password_api_v1_veupathdb_auth_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/veupathdb/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Logout
         * @description Clear local auth cookie and log out of VEuPathDB.
         */
        post: operations["logout_api_v1_veupathdb_auth_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/veupathdb/auth/refresh": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Refresh Internal Auth
         * @description Re-derive the internal ``pathfinder-auth`` token from a live VEuPathDB session.
         *
         *     Called on page load when the internal token is missing/expired but the
         *     VEuPathDB ``Authorization`` cookie is still valid.
         */
        post: operations["refresh_internal_auth_api_v1_veupathdb_auth_refresh_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/veupathdb/auth/status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Auth Status
         * @description Return current VEuPathDB auth status.
         *
         *     In mock mode (``PATHFINDER_CHAT_PROVIDER=mock``), a valid
         *     ``pathfinder-auth`` cookie is sufficient — the dev-login endpoint
         *     doesn't create a VEuPathDB session, so we skip the real WDK call.
         */
        get: operations["auth_status_api_v1_veupathdb_auth_status_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/operations/{operation_id}/subscribe": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Subscribe
         * @description SSE stream backed by Redis Streams.
         *
         *     Catchup: replays events from `lastEventId` (or from the beginning).
         *     Live: uses XREAD BLOCK for new events until a terminal event is seen.
         */
        get: operations["subscribe_api_v1_operations__operation_id__subscribe_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/operations/{operation_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Cancel
         * @description Cancel a running operation.
         *
         *     For chat operations this cancels the background asyncio task running
         *     the LLM agent. The producer's CancelledError handler emits a
         *     ``message_end`` event so any connected subscribers close cleanly.
         */
        post: operations["cancel_api_v1_operations__operation_id__cancel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/operations/active": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Active
         * @description List active operations, optionally filtered by stream and/or type.
         */
        get: operations["list_active_api_v1_operations_active_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/gene-sets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Gene Sets
         * @description List all gene sets for the current user, optionally filtered by site.
         */
        get: operations["list_gene_sets_api_v1_gene_sets_get"];
        put?: never;
        /**
         * Create Gene Set
         * @description Create a new gene set.
         */
        post: operations["create_gene_set_api_v1_gene_sets_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/gene-sets/{gene_set_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Gene Set
         * @description Get a gene set by ID.
         */
        get: operations["get_gene_set_api_v1_gene_sets__gene_set_id__get"];
        put?: never;
        post?: never;
        /**
         * Delete Gene Set
         * @description Delete a gene set.
         */
        delete: operations["delete_gene_set_api_v1_gene_sets__gene_set_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/gene-sets/operations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Set Operations
         * @description Perform set operations (intersect, union, minus) between two gene sets.
         */
        post: operations["set_operations_api_v1_gene_sets_operations_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/gene-sets/reverse-search": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Reverse Search
         * @description Rank the user's gene sets by how well they recover the given positive genes.
         */
        post: operations["reverse_search_api_v1_gene_sets_reverse_search_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/gene-sets/ensemble": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Ensemble Scoring
         * @description Score genes by frequency across multiple gene sets.
         */
        post: operations["ensemble_scoring_api_v1_gene_sets_ensemble_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/gene-sets/{gene_set_id}/enrich": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Enrich Gene Set
         * @description Run enrichment analysis on a gene set.
         */
        post: operations["enrich_gene_set_api_v1_gene_sets__gene_set_id__enrich_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/gene-sets/{gene_set_id}/results/attributes": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Gene Set Attributes
         * @description Get available attributes for a gene set's record type.
         */
        get: operations["get_gene_set_attributes_api_v1_gene_sets__gene_set_id__results_attributes_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/gene-sets/{gene_set_id}/results/records": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Gene Set Records
         * @description Get paginated result records for a gene set.
         */
        get: operations["get_gene_set_records_api_v1_gene_sets__gene_set_id__results_records_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/gene-sets/{gene_set_id}/results/distributions/{attribute_name}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Gene Set Distribution
         * @description Get distribution data for an attribute using the byValue column reporter.
         */
        get: operations["get_gene_set_distribution_api_v1_gene_sets__gene_set_id__results_distributions__attribute_name__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/gene-sets/{gene_set_id}/results/record": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Get Gene Set Record Detail
         * @description Get a single record's full details by primary key.
         */
        post: operations["get_gene_set_record_detail_api_v1_gene_sets__gene_set_id__results_record_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/gene-sets/confidence": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Gene Confidence
         * @description Compute per-gene composite confidence scores from classification data.
         */
        post: operations["gene_confidence_api_v1_gene_sets_confidence_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/exports/{export_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Download Export
         * @description Serve a previously generated export file.
         *
         *     Export IDs are uuid4 tokens with a 10-minute TTL. No auth required.
         */
        get: operations["download_export_api_v1_exports__export_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/internal/sse-schemas": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Sse Schemas
         * @description SSE event data schemas -- for OpenAPI generation only.
         */
        get: operations["sse_schemas_api_v1_internal_sse_schemas_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/internal/experiment-schemas": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Experiment Schemas
         * @description Experiment response schemas -- for OpenAPI generation only.
         */
        get: operations["experiment_schemas_api_v1_internal_experiment_schemas_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/user/data": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Purge User Data Endpoint
         * @description Purge user data from all local stores.
         *
         *     When ``deleteWdk=false`` (default): non-WDK streams are hard-deleted,
         *     WDK-linked projections are **dismissed** so WDK sync won't re-import
         *     them. The strategies remain on VEuPathDB but PathFinder ignores them.
         *
         *     When ``deleteWdk=true``: everything is hard-deleted locally AND all
         *     WDK strategies are deleted from VEuPathDB.
         *
         *     Always deletes: gene sets, experiments, control sets, Redis streams.
         *
         *     Pass ``?siteId=X`` to limit to one site, or omit for everything.
         */
        delete: operations["purge_user_data_endpoint_api_v1_user_data_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/eval/build-gold": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Build Gold Strategy Endpoint
         * @description Materialize a gold strategy AST on WDK and fetch all result gene IDs.
         */
        post: operations["build_gold_strategy_endpoint_api_v1_eval_build_gold_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/eval/strategy-gene-ids": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Get Strategy Gene Ids
         * @description Fetch all gene IDs from a PathFinder strategy's WDK root step.
         */
        post: operations["get_strategy_gene_ids_api_v1_eval_strategy_gene_ids_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
};

export type webhooks = Record<string, never>;

export type components = {
    schemas: {
        /**
         * AssistantDeltaEventData
         * @description Payload for ``assistant_delta`` SSE events (streaming tokens).
         */
        AssistantDeltaEventData: {
            /** Messageid */
            messageId?: string | null;
            /** Delta */
            delta?: string | null;
        };
        /**
         * AssistantMessageEventData
         * @description Payload for ``assistant_message`` SSE events (complete message).
         */
        AssistantMessageEventData: {
            /** Messageid */
            messageId?: string | null;
            /** Content */
            content?: string | null;
        };
        /**
         * AuthStatusResponse
         * @description Current auth status response.
         */
        AuthStatusResponse: {
            /** Signedin */
            signedIn: boolean;
            /** Name */
            name?: string | null;
            /** Email */
            email?: string | null;
        };
        /**
         * AuthSuccessResponse
         * @description Success response. Auth token is set via httpOnly cookie only.
         */
        AuthSuccessResponse: {
            /** Success */
            success: boolean;
        };
        /**
         * BatchOrganismTargetRequest
         * @description Per-organism override for a cross-organism batch experiment.
         */
        BatchOrganismTargetRequest: {
            /** Organism */
            organism: string;
            /** Positivecontrols */
            positiveControls?: string[] | null;
            /** Negativecontrols */
            negativeControls?: string[] | null;
        };
        /**
         * BenchmarkControlSet
         * @description A single control set within a benchmark suite.
         */
        BenchmarkControlSet: {
            /** Label */
            label: string;
            /** Positivecontrols */
            positiveControls: string[];
            /** Negativecontrols */
            negativeControls: string[];
            /** Controlsetid */
            controlSetId?: string | null;
            /**
             * Isprimary
             * @default false
             */
            isPrimary: boolean;
        };
        /**
         * BootstrapResultResponse
         * @description Robustness assessment via bootstrap resampling.
         */
        BootstrapResultResponse: {
            /**
             * Niterations
             * @default 0
             */
            nIterations: number;
            /** Metriccis */
            metricCis?: {
                [key: string]: components["schemas"]["ConfidenceIntervalResponse"];
            };
            /** Rankmetriccis */
            rankMetricCis?: {
                [key: string]: components["schemas"]["ConfidenceIntervalResponse"];
            };
            /**
             * Topkstability
             * @default 0
             */
            topKStability: number;
            /** Negativesetsensitivity */
            negativeSetSensitivity?: components["schemas"]["NegativeSetVariantResponse"][];
        };
        /**
         * BuildGoldRequest
         * @description Request to materialize a gold strategy AST on WDK and return gene IDs.
         */
        BuildGoldRequest: {
            /** Goldid */
            goldId: string;
            /** Siteid */
            siteId: string;
            /**
             * Recordtype
             * @default gene
             */
            recordType: string;
            /** Steptree */
            stepTree: {
                [key: string]: unknown;
            };
        };
        /** BuildGoldResponse */
        BuildGoldResponse: {
            /** Goldid */
            goldId: string;
            /** Wdkstrategyid */
            wdkStrategyId: number;
            /** Rootstepid */
            rootStepId: number;
            /** Estimatedsize */
            estimatedSize: number;
            /** Geneids */
            geneIds: string[];
        };
        /**
         * ChatMention
         * @description A reference to a strategy or experiment included via @-mention.
         */
        ChatMention: {
            /**
             * Type
             * @enum {string}
             */
            type: "strategy" | "experiment";
            /** Id */
            id: string;
            /** Displayname */
            displayName: string;
        };
        /**
         * ChatRequest
         * @description Request to send a chat message.
         */
        ChatRequest: {
            /** Strategyid */
            strategyId?: string | null;
            /** Siteid */
            siteId: string;
            /** Message */
            message: string;
            /** Provider */
            provider?: ("openai" | "anthropic" | "google" | "ollama" | "mock") | null;
            /** Model */
            model?: string | null;
            /** Reasoningeffort */
            reasoningEffort?: ("none" | "low" | "medium" | "high") | null;
            /**
             * Disablerag
             * @default false
             */
            disableRag: boolean;
            /** Temperature */
            temperature?: number | null;
            /** Seed */
            seed?: number | null;
            /** Contextsize */
            contextSize?: number | null;
            /** Responsetokens */
            responseTokens?: number | null;
            /** Reasoningbudget */
            reasoningBudget?: number | null;
            /** Disabledtools */
            disabledTools?: string[];
            /** Mentions */
            mentions?: components["schemas"]["ChatMention"][];
        };
        /**
         * CitationResponse
         * @description Citation from research tools.
         */
        CitationResponse: {
            /** Id */
            id: string;
            /** Source */
            source: string;
            /** Tag */
            tag?: string | null;
            /** Title */
            title: string;
            /** Url */
            url?: string | null;
            /** Authors */
            authors?: string[] | null;
            /** Year */
            year?: number | null;
            /** Doi */
            doi?: string | null;
            /** Pmid */
            pmid?: string | null;
            /** Snippet */
            snippet?: string | null;
            /** Accessedat */
            accessedAt?: string | null;
        };
        /**
         * CitationsEventData
         * @description Payload for ``citations`` SSE events.
         */
        CitationsEventData: {
            /** Citations */
            citations?: components["schemas"]["CitationResponse"][] | null;
        };
        /**
         * ColocationParams
         * @description Parameters for colocation operator.
         *
         *     WDK fields: upstream (int), downstream (int), strand (same|opposite|both).
         */
        ColocationParams: {
            /**
             * Upstream
             * @default 0
             */
            upstream: number;
            /**
             * Downstream
             * @default 0
             */
            downstream: number;
            /**
             * Strand
             * @default both
             * @enum {string}
             */
            strand: "same" | "opposite" | "both";
        };
        /**
         * CombineOp
         * @description Set operations for combining two step results.
         * @enum {string}
         */
        CombineOp: "INTERSECT" | "MINUS" | "RMINUS" | "LONLY" | "RONLY" | "COLOCATE" | "UNION";
        /**
         * ConfidenceIntervalResponse
         * @description Bootstrap confidence interval for a single metric.
         */
        ConfidenceIntervalResponse: {
            /**
             * Lower
             * @default 0
             */
            lower: number;
            /**
             * Mean
             * @default 0
             */
            mean: number;
            /**
             * Upper
             * @default 0
             */
            upper: number;
            /**
             * Std
             * @default 0
             */
            std: number;
        };
        /**
         * ConfusionMatrixResponse
         * @description 2x2 confusion matrix counts.
         */
        ConfusionMatrixResponse: {
            /** Truepositives */
            truePositives: number;
            /** Falsepositives */
            falsePositives: number;
            /** Truenegatives */
            trueNegatives: number;
            /** Falsenegatives */
            falseNegatives: number;
        };
        /**
         * ControlSetResponse
         * @description Serialized control set returned to the client.
         */
        ControlSetResponse: {
            /** Id */
            id: string;
            /** Name */
            name: string;
            /** Siteid */
            siteId: string;
            /** Recordtype */
            recordType: string;
            /** Positiveids */
            positiveIds: string[];
            /** Negativeids */
            negativeIds: string[];
            /** Source */
            source?: string | null;
            /** Tags */
            tags: string[];
            /** Provenancenotes */
            provenanceNotes?: string | null;
            /** Version */
            version: number;
            /** Ispublic */
            isPublic: boolean;
            /** Userid */
            userId?: string | null;
            /** Createdat */
            createdAt: string;
        };
        /**
         * ControlSetSummaryResponse
         * @description Control set summary for listing.
         */
        ControlSetSummaryResponse: {
            /** Id */
            id: string;
            /** Name */
            name: string;
            /** Source */
            source: string;
            /** Organism */
            organism?: string | null;
            /** Positivecount */
            positiveCount: number;
            /** Negativecount */
            negativeCount: number;
        };
        /**
         * CreateBatchExperimentRequest
         * @description Request to run the same search across multiple organisms.
         */
        CreateBatchExperimentRequest: {
            base: components["schemas"]["CreateExperimentRequest"];
            /** Organismparamname */
            organismParamName: string;
            /** Targetorganisms */
            targetOrganisms: components["schemas"]["BatchOrganismTargetRequest"][];
        };
        /**
         * CreateBenchmarkRequest
         * @description Request to run a benchmark suite across multiple control sets.
         */
        CreateBenchmarkRequest: {
            base: components["schemas"]["CreateExperimentRequest"];
            /** Controlsets */
            controlSets: components["schemas"]["BenchmarkControlSet"][];
        };
        /**
         * CreateControlSetRequest
         * @description Payload for creating a new control set.
         */
        CreateControlSetRequest: {
            /** Name */
            name: string;
            /** Siteid */
            siteId: string;
            /** Recordtype */
            recordType: string;
            /** Positiveids */
            positiveIds?: string[];
            /** Negativeids */
            negativeIds?: string[];
            /** Source */
            source?: string | null;
            /** Tags */
            tags?: string[];
            /** Provenancenotes */
            provenanceNotes?: string | null;
            /**
             * Ispublic
             * @default false
             */
            isPublic: boolean;
        };
        /**
         * CreateExperimentRequest
         * @description Request to create and run an experiment.
         *
         *     Supports three modes: ``single`` (default), ``multi-step``, and ``import``.
         */
        CreateExperimentRequest: {
            /** Siteid */
            siteId: string;
            /** Recordtype */
            recordType: string;
            /**
             * Mode
             * @default single
             * @enum {string}
             */
            mode: "single" | "multi-step" | "import";
            /**
             * Searchname
             * @default
             */
            searchName: string;
            parameters?: components["schemas"]["JSONObject"];
            stepTree?: components["schemas"]["JSONValue"];
            /** Sourcestrategyid */
            sourceStrategyId?: string | null;
            /** Optimizationtargetstep */
            optimizationTargetStep?: string | null;
            /** Positivecontrols */
            positiveControls: string[];
            /** Negativecontrols */
            negativeControls: string[];
            /** Controlssearchname */
            controlsSearchName: string;
            /** Controlsparamname */
            controlsParamName: string;
            /**
             * Controlsvalueformat
             * @default newline
             * @enum {string}
             */
            controlsValueFormat: "newline" | "json_list" | "comma";
            /**
             * Enablecrossvalidation
             * @default false
             */
            enableCrossValidation: boolean;
            /**
             * Kfolds
             * @default 5
             */
            kFolds: number;
            /** Enrichmenttypes */
            enrichmentTypes?: ("go_function" | "go_component" | "go_process" | "pathway" | "word")[];
            /**
             * Name
             * @default Untitled Experiment
             */
            name: string;
            /**
             * Description
             * @default
             */
            description: string;
            /** Optimizationspecs */
            optimizationSpecs?: components["schemas"]["OptimizationSpecRequest"][] | null;
            /**
             * Optimizationbudget
             * @default 30
             */
            optimizationBudget: number;
            /** Optimizationobjective */
            optimizationObjective?: ("f1" | "f_beta" | "recall" | "precision" | "specificity" | "balanced_accuracy" | "mcc" | "youdens_j" | "custom") | null;
            parameterDisplayValues?: components["schemas"]["JSONObject"] | null;
            /**
             * Enablestepanalysis
             * @default false
             */
            enableStepAnalysis: boolean;
            /** Stepanalysisphases */
            stepAnalysisPhases?: string[] | null;
            /** Controlsetid */
            controlSetId?: string | null;
            /** Thresholdknobs */
            thresholdKnobs?: components["schemas"]["ThresholdKnobRequest"][] | null;
            /** Operatorknobs */
            operatorKnobs?: components["schemas"]["OperatorKnobRequest"][] | null;
            /**
             * Treeoptimizationobjective
             * @default precision_at_50
             */
            treeOptimizationObjective: string;
            /**
             * Treeoptimizationbudget
             * @default 50
             */
            treeOptimizationBudget: number;
            /** Maxlistsize */
            maxListSize?: number | null;
            /** Sortattribute */
            sortAttribute?: string | null;
            /**
             * Sortdirection
             * @default ASC
             * @enum {string}
             */
            sortDirection: "ASC" | "DESC";
            /** Parentexperimentid */
            parentExperimentId?: string | null;
            /** Targetgeneids */
            targetGeneIds?: string[] | null;
        };
        /**
         * CreateGeneSetRequest
         * @description Create a gene set from IDs, strategy, or upload.
         */
        CreateGeneSetRequest: {
            /** Name */
            name: string;
            /** Siteid */
            siteId: string;
            /** Geneids */
            geneIds: string[];
            /**
             * Source
             * @default paste
             * @enum {string}
             */
            source: "strategy" | "paste" | "upload" | "derived" | "saved";
            /** Wdkstrategyid */
            wdkStrategyId?: number | null;
            /** Wdkstepid */
            wdkStepId?: number | null;
            /** Searchname */
            searchName?: string | null;
            /** Recordtype */
            recordType?: string | null;
            /** Parameters */
            parameters?: {
                [key: string]: string;
            } | null;
        };
        /**
         * CreateStrategyRequest
         * @description Request to create a strategy.
         */
        CreateStrategyRequest: {
            /** Name */
            name: string;
            /** Siteid */
            siteId: string;
            plan: components["schemas"]["StrategyPlanPayload-Input"];
        };
        /**
         * CrossValidationResultResponse
         * @description Aggregated cross-validation result.
         */
        CrossValidationResultResponse: {
            /** K */
            k: number;
            /** Folds */
            folds: components["schemas"]["FoldMetricsResponse"][];
            meanMetrics: components["schemas"]["ExperimentMetricsResponse"];
            /** Stdmetrics */
            stdMetrics?: {
                [key: string]: number;
            };
            /**
             * Overfittingscore
             * @default 0
             */
            overfittingScore: number;
            /**
             * Overfittinglevel
             * @default low
             */
            overfittingLevel: string;
        };
        /**
         * CustomEnrichRequest
         * @description Request to run a custom gene-set enrichment test.
         */
        CustomEnrichRequest: {
            /** Genesetname */
            geneSetName: string;
            /** Geneids */
            geneIds: string[];
        };
        /**
         * CustomEnrichmentResult
         * @description Return shape of :func:`run_custom_enrichment`.
         */
        CustomEnrichmentResult: {
            /** Genesetname */
            geneSetName: string;
            /** Genesetsize */
            geneSetSize: number;
            /** Overlapcount */
            overlapCount: number;
            /** Overlapgenes */
            overlapGenes: string[];
            /** Backgroundsize */
            backgroundSize: number;
            /** Tpcount */
            tpCount: number;
            /** Foldenrichment */
            foldEnrichment: number;
            /** Pvalue */
            pValue: number;
            /** Oddsratio */
            oddsRatio: number;
        };
        /**
         * EnrichmentCompareRequest
         * @description Request to compare enrichment results across experiments.
         */
        EnrichmentCompareRequest: {
            /** Experimentids */
            experimentIds: string[];
            /** Analysistype */
            analysisType?: string | null;
        };
        /**
         * EnrichmentCompareResult
         * @description Return shape of :func:`compare_enrichment_across`.
         */
        EnrichmentCompareResult: {
            /** Experimentids */
            experimentIds: string[];
            /** Experimentlabels */
            experimentLabels: {
                [key: string]: string;
            };
            /** Rows */
            rows: components["schemas"]["EnrichmentRow"][];
            /** Totalterms */
            totalTerms: number;
        };
        /**
         * EnrichmentResultResponse
         * @description Results for a single enrichment analysis type.
         */
        EnrichmentResultResponse: {
            /**
             * Analysistype
             * @enum {string}
             */
            analysisType: "go_function" | "go_component" | "go_process" | "pathway" | "word";
            /** Terms */
            terms: components["schemas"]["EnrichmentTermResponse"][];
            /**
             * Totalgenesanalyzed
             * @default 0
             */
            totalGenesAnalyzed: number;
            /**
             * Backgroundsize
             * @default 0
             */
            backgroundSize: number;
            /** Error */
            error?: string | null;
        };
        /**
         * EnrichmentRow
         * @description Shape of one term row in the enrichment comparison.
         */
        EnrichmentRow: {
            /** Termkey */
            termKey: string;
            /** Termname */
            termName: string;
            /** Analysistype */
            analysisType: string;
            /** Scores */
            scores: {
                [key: string]: components["schemas"]["JSONValue"];
            };
            /** Maxscore */
            maxScore: number;
            /** Experimentcount */
            experimentCount: number;
        };
        /**
         * EnrichmentTermResponse
         * @description Single enriched term from WDK analysis.
         */
        EnrichmentTermResponse: {
            /** Termid */
            termId: string;
            /** Termname */
            termName: string;
            /** Genecount */
            geneCount: number;
            /** Backgroundcount */
            backgroundCount: number;
            /** Foldenrichment */
            foldEnrichment: number;
            /** Oddsratio */
            oddsRatio: number;
            /** Pvalue */
            pValue: number;
            /** Fdr */
            fdr: number;
            /** Bonferroni */
            bonferroni: number;
            /** Genes */
            genes?: string[];
        };
        /**
         * EnsembleScore
         * @description A single gene's ensemble score.
         */
        EnsembleScore: {
            /** Geneid */
            geneId: string;
            /** Frequency */
            frequency: number;
            /** Count */
            count: number;
            /** Total */
            total: number;
            /** Inpositives */
            inPositives: boolean;
        };
        /**
         * EnsembleScoringRequest
         * @description Compute ensemble frequency scores across multiple gene sets.
         */
        EnsembleScoringRequest: {
            /** Genesetids */
            geneSetIds: string[];
            /** Positivecontrols */
            positiveControls?: string[] | null;
        };
        /**
         * ErrorEventData
         * @description Payload for ``error`` SSE events.
         */
        ErrorEventData: {
            /** Error */
            error: string;
        };
        /**
         * ExecutorBuildRequestEventData
         * @description Payload for ``executor_build_request`` SSE events.
         */
        ExecutorBuildRequestEventData: {
            executorBuildRequest?: components["schemas"]["JSONObject"] | null;
        };
        /**
         * ExperimentConfigResponse
         * @description Full configuration for an experiment run.
         */
        ExperimentConfigResponse: {
            /** Siteid */
            siteId: string;
            /** Recordtype */
            recordType: string;
            /** Searchname */
            searchName: string;
            parameters: components["schemas"]["JSONObject"];
            /** Positivecontrols */
            positiveControls: string[];
            /** Negativecontrols */
            negativeControls: string[];
            /** Controlssearchname */
            controlsSearchName: string;
            /** Controlsparamname */
            controlsParamName: string;
            /**
             * Controlsvalueformat
             * @default newline
             * @enum {string}
             */
            controlsValueFormat: "newline" | "json_list" | "comma";
            /**
             * Enablecrossvalidation
             * @default false
             */
            enableCrossValidation: boolean;
            /**
             * Kfolds
             * @default 5
             */
            kFolds: number;
            /** Enrichmenttypes */
            enrichmentTypes?: ("go_function" | "go_component" | "go_process" | "pathway" | "word")[];
            /**
             * Name
             * @default
             */
            name: string;
            /**
             * Description
             * @default
             */
            description: string;
            /** Optimizationspecs */
            optimizationSpecs?: components["schemas"]["OptimizationSpecResponse"][] | null;
            /**
             * Optimizationbudget
             * @default 30
             */
            optimizationBudget: number;
            /**
             * Optimizationobjective
             * @default balanced_accuracy
             * @enum {string}
             */
            optimizationObjective: "f1" | "f_beta" | "recall" | "precision" | "specificity" | "balanced_accuracy" | "mcc" | "youdens_j" | "custom";
            /** Parameterdisplayvalues */
            parameterDisplayValues?: {
                [key: string]: string;
            } | null;
            /**
             * Mode
             * @default single
             * @enum {string}
             */
            mode: "single" | "multi-step" | "import";
            stepTree?: components["schemas"]["JSONValue"];
            /** Sourcestrategyid */
            sourceStrategyId?: string | null;
            /** Optimizationtargetstep */
            optimizationTargetStep?: string | null;
            /**
             * Enablestepanalysis
             * @default false
             */
            enableStepAnalysis: boolean;
            /** Stepanalysisphases */
            stepAnalysisPhases?: string[];
            /** Controlsetid */
            controlSetId?: string | null;
            /** Thresholdknobs */
            thresholdKnobs?: components["schemas"]["ThresholdKnobResponse"][] | null;
            /** Operatorknobs */
            operatorKnobs?: components["schemas"]["OperatorKnobResponse"][] | null;
            /**
             * Treeoptimizationobjective
             * @default precision_at_50
             */
            treeOptimizationObjective: string;
            /**
             * Treeoptimizationbudget
             * @default 50
             */
            treeOptimizationBudget: number;
            /** Maxlistsize */
            maxListSize?: number | null;
            /** Sortattribute */
            sortAttribute?: string | null;
            /**
             * Sortdirection
             * @default ASC
             */
            sortDirection: string;
            /** Parentexperimentid */
            parentExperimentId?: string | null;
            /** Targetgeneids */
            targetGeneIds?: string[] | null;
        };
        /**
         * ExperimentMetricsResponse
         * @description Full classification metrics derived from a confusion matrix.
         */
        ExperimentMetricsResponse: {
            confusionMatrix: components["schemas"]["ConfusionMatrixResponse"];
            /** Sensitivity */
            sensitivity: number;
            /** Specificity */
            specificity: number;
            /** Precision */
            precision: number;
            /** F1Score */
            f1Score: number;
            /** Mcc */
            mcc: number;
            /** Balancedaccuracy */
            balancedAccuracy: number;
            /**
             * Negativepredictivevalue
             * @default 0
             */
            negativePredictiveValue: number;
            /**
             * Falsepositiverate
             * @default 0
             */
            falsePositiveRate: number;
            /**
             * Falsenegativerate
             * @default 0
             */
            falseNegativeRate: number;
            /**
             * Youdensj
             * @default 0
             */
            youdensJ: number;
            /**
             * Totalresults
             * @default 0
             */
            totalResults: number;
            /**
             * Totalpositives
             * @default 0
             */
            totalPositives: number;
            /**
             * Totalnegatives
             * @default 0
             */
            totalNegatives: number;
        };
        /**
         * ExperimentProgressDataResponse
         * @description Progress data for experiment execution.
         */
        ExperimentProgressDataResponse: {
            /** Phase */
            phase: string;
            /** Message */
            message?: string | null;
            trialProgress?: components["schemas"]["TrialProgressDataResponse"] | null;
            stepAnalysisProgress?: components["schemas"]["StepAnalysisProgressDataResponse"] | null;
        };
        /**
         * ExperimentResponse
         * @description Full experiment with config and results.
         */
        ExperimentResponse: {
            /** Id */
            id: string;
            config: components["schemas"]["ExperimentConfigResponse"];
            /** Userid */
            userId?: string | null;
            /**
             * Status
             * @default pending
             * @enum {string}
             */
            status: "pending" | "running" | "completed" | "error" | "cancelled";
            metrics?: components["schemas"]["ExperimentMetricsResponse"] | null;
            crossValidation?: components["schemas"]["CrossValidationResultResponse"] | null;
            /** Enrichmentresults */
            enrichmentResults?: components["schemas"]["EnrichmentResultResponse"][];
            /** Truepositivegenes */
            truePositiveGenes?: components["schemas"]["GeneInfoResponse"][];
            /** Falsenegativegenes */
            falseNegativeGenes?: components["schemas"]["GeneInfoResponse"][];
            /** Falsepositivegenes */
            falsePositiveGenes?: components["schemas"]["GeneInfoResponse"][];
            /** Truenegativegenes */
            trueNegativeGenes?: components["schemas"]["GeneInfoResponse"][];
            /** Error */
            error?: string | null;
            /** Totaltimeseconds */
            totalTimeSeconds?: number | null;
            /**
             * Createdat
             * @default
             */
            createdAt: string;
            /** Completedat */
            completedAt?: string | null;
            /** Batchid */
            batchId?: string | null;
            /** Benchmarkid */
            benchmarkId?: string | null;
            /** Controlsetlabel */
            controlSetLabel?: string | null;
            /**
             * Isprimarybenchmark
             * @default false
             */
            isPrimaryBenchmark: boolean;
            optimizationResult?: components["schemas"]["JSONObject"] | null;
            /** Wdkstrategyid */
            wdkStrategyId?: number | null;
            /** Wdkstepid */
            wdkStepId?: number | null;
            /** Notes */
            notes?: string | null;
            stepAnalysis?: components["schemas"]["StepAnalysisResultResponse"] | null;
            rankMetrics?: components["schemas"]["RankMetricsResponse"] | null;
            robustness?: components["schemas"]["BootstrapResultResponse"] | null;
            treeOptimization?: components["schemas"]["TreeOptimizationResultResponse"] | null;
        };
        /**
         * ExperimentSchemaIndex
         * @description Index of all experiment response schemas. Never called -- exists for OpenAPI generation.
         */
        ExperimentSchemaIndex: {
            experiment?: components["schemas"]["ExperimentResponse"] | null;
            experiment_summary?: components["schemas"]["ExperimentSummaryResponse"] | null;
            experiment_config?: components["schemas"]["ExperimentConfigResponse"] | null;
            confusion_matrix?: components["schemas"]["ConfusionMatrixResponse"] | null;
            experiment_metrics?: components["schemas"]["ExperimentMetricsResponse"] | null;
            gene_info?: components["schemas"]["GeneInfoResponse"] | null;
            fold_metrics?: components["schemas"]["FoldMetricsResponse"] | null;
            cross_validation_result?: components["schemas"]["CrossValidationResultResponse"] | null;
            enrichment_term?: components["schemas"]["EnrichmentTermResponse"] | null;
            enrichment_result?: components["schemas"]["EnrichmentResultResponse"] | null;
            rank_metrics?: components["schemas"]["RankMetricsResponse"] | null;
            confidence_interval?: components["schemas"]["ConfidenceIntervalResponse"] | null;
            negative_set_variant?: components["schemas"]["NegativeSetVariantResponse"] | null;
            bootstrap_result?: components["schemas"]["BootstrapResultResponse"] | null;
            step_evaluation?: components["schemas"]["StepEvaluationResponse"] | null;
            operator_variant?: components["schemas"]["OperatorVariantResponse"] | null;
            operator_comparison?: components["schemas"]["OperatorComparisonResponse"] | null;
            step_contribution?: components["schemas"]["StepContributionResponse"] | null;
            parameter_sweep_point?: components["schemas"]["ParameterSweepPointResponse"] | null;
            parameter_sensitivity?: components["schemas"]["ParameterSensitivityResponse"] | null;
            step_analysis_result?: components["schemas"]["StepAnalysisResultResponse"] | null;
            optimization_spec?: components["schemas"]["OptimizationSpecResponse"] | null;
            threshold_knob?: components["schemas"]["ThresholdKnobResponse"] | null;
            operator_knob?: components["schemas"]["OperatorKnobResponse"] | null;
            tree_optimization_trial?: components["schemas"]["TreeOptimizationTrialResponse"] | null;
            tree_optimization_result?: components["schemas"]["TreeOptimizationResultResponse"] | null;
            trial_progress_data?: components["schemas"]["TrialProgressDataResponse"] | null;
            step_analysis_progress_data?: components["schemas"]["StepAnalysisProgressDataResponse"] | null;
            experiment_progress_data?: components["schemas"]["ExperimentProgressDataResponse"] | null;
            optimization_result?: components["schemas"]["OptimizationResultResponse"] | null;
            control_set_summary?: components["schemas"]["ControlSetSummaryResponse"] | null;
            citation?: components["schemas"]["CitationResponse"] | null;
            planning_artifact?: components["schemas"]["PlanningArtifactResponse"] | null;
        };
        /**
         * ExperimentSummaryResponse
         * @description Lightweight experiment summary for list views.
         */
        ExperimentSummaryResponse: {
            /** Id */
            id: string;
            /** Name */
            name: string;
            /** Siteid */
            siteId: string;
            /** Searchname */
            searchName: string;
            /** Recordtype */
            recordType: string;
            /**
             * Mode
             * @enum {string}
             */
            mode: "single" | "multi-step" | "import";
            /**
             * Status
             * @enum {string}
             */
            status: "pending" | "running" | "completed" | "error" | "cancelled";
            /** F1Score */
            f1Score?: number | null;
            /** Sensitivity */
            sensitivity?: number | null;
            /** Specificity */
            specificity?: number | null;
            /** Totalpositives */
            totalPositives: number;
            /** Totalnegatives */
            totalNegatives: number;
            /** Createdat */
            createdAt: string;
            /** Batchid */
            batchId?: string | null;
            /** Benchmarkid */
            benchmarkId?: string | null;
            /** Controlsetlabel */
            controlSetLabel?: string | null;
            /**
             * Isprimarybenchmark
             * @default false
             */
            isPrimaryBenchmark: boolean;
        };
        /**
         * FetchGeneIdsRequest
         * @description Fetch gene IDs from an existing PathFinder strategy.
         */
        FetchGeneIdsRequest: {
            /** Strategyid */
            strategyId: string;
            /** Siteid */
            siteId: string;
        };
        /**
         * FoldMetricsResponse
         * @description Metrics for a single cross-validation fold.
         */
        FoldMetricsResponse: {
            /** Foldindex */
            foldIndex: number;
            metrics: components["schemas"]["ExperimentMetricsResponse"];
            /** Positivecontrolids */
            positiveControlIds?: string[];
            /** Negativecontrolids */
            negativeControlIds?: string[];
        };
        /**
         * GeneConfidenceRequest
         * @description Compute per-gene confidence scores from classification data.
         */
        GeneConfidenceRequest: {
            /** Tpids */
            tpIds: string[];
            /** Fpids */
            fpIds: string[];
            /** Fnids */
            fnIds: string[];
            /** Tnids */
            tnIds: string[];
            /** Ensemblescores */
            ensembleScores?: {
                [key: string]: number;
            } | null;
            /** Enrichmentgenecounts */
            enrichmentGeneCounts?: {
                [key: string]: number;
            } | null;
            /**
             * Maxenrichmentterms
             * @default 1
             */
            maxEnrichmentTerms: number;
        };
        /**
         * GeneConfidenceScoreResponse
         * @description Single gene confidence score in the response.
         */
        GeneConfidenceScoreResponse: {
            /** Geneid */
            geneId: string;
            /** Compositescore */
            compositeScore: number;
            /** Classificationscore */
            classificationScore: number;
            /** Ensemblescore */
            ensembleScore: number;
            /** Enrichmentscore */
            enrichmentScore: number;
        };
        /**
         * GeneInfoResponse
         * @description Minimal gene metadata.
         */
        GeneInfoResponse: {
            /** Id */
            id: string;
            /** Name */
            name?: string | null;
            /** Organism */
            organism?: string | null;
            /** Product */
            product?: string | null;
        };
        /**
         * GeneMembership
         * @description Shape of one gene membership entry.
         */
        GeneMembership: {
            /** Geneid */
            geneId: string;
            /** Foundin */
            foundIn: number;
            /** Totalexperiments */
            totalExperiments: number;
            /** Experiments */
            experiments: string[];
        };
        /**
         * GeneResolveRequest
         * @description Request body for gene ID resolution.
         */
        GeneResolveRequest: {
            /** Geneids */
            geneIds: string[];
        };
        /**
         * GeneResolveResponse
         * @description Gene ID resolution response.
         */
        GeneResolveResponse: {
            /** Resolved */
            resolved: components["schemas"]["ResolvedGeneResponse"][];
            /** Unresolved */
            unresolved: string[];
        };
        /**
         * GeneSearchResponse
         * @description Paginated gene search response.
         */
        GeneSearchResponse: {
            /** Results */
            results: components["schemas"]["GeneSearchResultResponse"][];
            /** Totalcount */
            totalCount: number;
            /**
             * Suggestedorganisms
             * @default []
             */
            suggestedOrganisms: string[];
        };
        /**
         * GeneSearchResultResponse
         * @description A single gene result from site-search.
         */
        GeneSearchResultResponse: {
            /** Geneid */
            geneId: string;
            /**
             * Displayname
             * @default
             */
            displayName: string;
            /**
             * Organism
             * @default
             */
            organism: string;
            /**
             * Product
             * @default
             */
            product: string;
            /**
             * Genename
             * @default
             */
            geneName: string;
            /**
             * Genetype
             * @default
             */
            geneType: string;
            /**
             * Location
             * @default
             */
            location: string;
            /**
             * Matchedfields
             * @default []
             */
            matchedFields: string[];
        };
        /**
         * GeneSetEnrichRequest
         * @description Run enrichment on a gene set.
         */
        GeneSetEnrichRequest: {
            /** Enrichmenttypes */
            enrichmentTypes: ("go_function" | "go_component" | "go_process" | "pathway" | "word")[];
        };
        /**
         * GeneSetResponse
         * @description Gene set response DTO.
         */
        GeneSetResponse: {
            /** Id */
            id: string;
            /** Name */
            name: string;
            /** Siteid */
            siteId: string;
            /** Geneids */
            geneIds: string[];
            /**
             * Source
             * @enum {string}
             */
            source: "strategy" | "paste" | "upload" | "derived" | "saved";
            /** Genecount */
            geneCount: number;
            /** Wdkstrategyid */
            wdkStrategyId?: number | null;
            /** Wdkstepid */
            wdkStepId?: number | null;
            /** Searchname */
            searchName?: string | null;
            /** Recordtype */
            recordType?: string | null;
            /** Parameters */
            parameters?: {
                [key: string]: string;
            } | null;
            /** Parentsetids */
            parentSetIds?: string[];
            /** Operation */
            operation?: ("intersect" | "union" | "minus") | null;
            /** Createdat */
            createdAt: string;
            /**
             * Stepcount
             * @default 1
             */
            stepCount: number;
        };
        /**
         * GeneSetSummary
         * @description Summary of a gene set — nested model, not a top-level event.
         */
        GeneSetSummary: {
            /** Id */
            id?: string | null;
            /** Name */
            name?: string | null;
            /** Genecount */
            geneCount?: number | null;
            /** Source */
            source?: string | null;
            /** Siteid */
            siteId?: string | null;
        };
        /**
         * GraphClearedEventData
         * @description Payload for ``graph_cleared`` SSE events.
         */
        GraphClearedEventData: {
            /** Graphid */
            graphId?: string | null;
        };
        /**
         * GraphPlanEventData
         * @description Payload for ``graph_plan`` SSE events.
         */
        GraphPlanEventData: {
            /** Graphid */
            graphId?: string | null;
            plan?: components["schemas"]["JSONObject"] | null;
            /** Name */
            name?: string | null;
            /** Recordtype */
            recordType?: string | null;
            /** Description */
            description?: string | null;
        };
        /**
         * GraphSnapshotContent
         * @description Content of a graph_snapshot event payload.
         */
        GraphSnapshotContent: {
            /** Graphid */
            graphId?: string | null;
            /** Graphname */
            graphName?: string | null;
            /** Recordtype */
            recordType?: string | null;
            /** Name */
            name?: string | null;
            /** Description */
            description?: string | null;
            /** Rootstepid */
            rootStepId?: string | null;
            /** Steps */
            steps?: components["schemas"]["JSONObject"][];
            /** Edges */
            edges?: components["schemas"]["JSONObject"][];
            plan?: components["schemas"]["JSONObject"] | null;
        };
        /**
         * GraphSnapshotEventData
         * @description Payload for ``graph_snapshot`` SSE events.
         */
        GraphSnapshotEventData: {
            graphSnapshot?: components["schemas"]["GraphSnapshotContent"] | null;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /**
         * HealthResponse
         * @description Health check response.
         */
        HealthResponse: {
            /** Status */
            status: string;
            /** Version */
            version: string;
            /**
             * Timestamp
             * Format: date-time
             */
            timestamp: string;
        };
        JSONArray: components["schemas"]["JSONValue"][];
        JSONObject: {
            [key: string]: components["schemas"]["JSONValue"];
        };
        JSONValue: unknown;
        JsonValue: unknown;
        /** LoginPayload */
        LoginPayload: {
            /** Email */
            email: string;
            /** Password */
            password: string;
        };
        /**
         * MessageEndEventData
         * @description Payload for ``message_end`` SSE events — mirrors TokenUsageResponse.
         */
        MessageEndEventData: {
            /** Modelid */
            modelId?: string | null;
            /** Prompttokens */
            promptTokens?: number | null;
            /** Completiontokens */
            completionTokens?: number | null;
            /** Totaltokens */
            totalTokens?: number | null;
            /** Cachedtokens */
            cachedTokens?: number | null;
            /** Toolcallcount */
            toolCallCount?: number | null;
            /** Registeredtoolcount */
            registeredToolCount?: number | null;
            /** Llmcallcount */
            llmCallCount?: number | null;
            /** Subkaniprompttokens */
            subKaniPromptTokens?: number | null;
            /** Subkanicompletiontokens */
            subKaniCompletionTokens?: number | null;
            /** Subkanicallcount */
            subKaniCallCount?: number | null;
            /** Estimatedcostusd */
            estimatedCostUsd?: number | null;
        };
        /**
         * MessageResponse
         * @description Chat message.
         */
        MessageResponse: {
            /** Role */
            role: string;
            /** Content */
            content: string;
            /** Modelid */
            modelId?: string | null;
            /** Toolcalls */
            toolCalls?: components["schemas"]["ToolCallResponse"][] | null;
            subKaniActivity?: components["schemas"]["SubKaniActivityResponse"] | null;
            /** Citations */
            citations?: components["schemas"]["CitationResponse"][] | null;
            /** Planningartifacts */
            planningArtifacts?: components["schemas"]["PlanningArtifactResponse"][] | null;
            /** Reasoning */
            reasoning?: string | null;
            optimizationProgress?: components["schemas"]["OptimizationProgressEventData"] | null;
            tokenUsage?: components["schemas"]["TokenUsageResponse"] | null;
            /**
             * Timestamp
             * Format: date-time
             */
            timestamp: string;
        };
        /**
         * MessageStartEventData
         * @description Payload for ``message_start`` SSE events.
         */
        MessageStartEventData: {
            /** Strategyid */
            strategyId?: string | null;
            strategy?: components["schemas"]["JSONObject"] | null;
        };
        /**
         * ModelCatalogEntryResponse
         * @description A single model in the catalog — for API responses.
         */
        ModelCatalogEntryResponse: {
            /** Id */
            id: string;
            /** Name */
            name: string;
            /**
             * Provider
             * @enum {string}
             */
            provider: "openai" | "anthropic" | "google" | "ollama" | "mock";
            /** Model */
            model: string;
            /**
             * Description
             * @default
             */
            description: string;
            /**
             * Supportsreasoning
             * @default false
             */
            supportsReasoning: boolean;
            /**
             * Enabled
             * @default true
             */
            enabled: boolean;
            /**
             * Contextsize
             * @default 0
             */
            contextSize: number;
            /**
             * Defaultreasoningbudget
             * @default 0
             */
            defaultReasoningBudget: number;
            /**
             * Inputprice
             * @default 0
             */
            inputPrice: number;
            /**
             * Cachedinputprice
             * @default 0
             */
            cachedInputPrice: number;
            /**
             * Outputprice
             * @default 0
             */
            outputPrice: number;
        };
        /**
         * ModelListResponse
         * @description Response for the /models endpoint.
         */
        ModelListResponse: {
            /** Models */
            models: components["schemas"]["ModelCatalogEntryResponse"][];
            /** Default */
            default: string;
            /**
             * Defaultreasoningeffort
             * @enum {string}
             */
            defaultReasoningEffort: "none" | "low" | "medium" | "high";
        };
        /**
         * ModelSelectedEventData
         * @description Payload for ``model_selected`` SSE events.
         */
        ModelSelectedEventData: {
            /** Modelid */
            modelId: string;
        };
        /**
         * NegativeSetVariantResponse
         * @description Rank metrics evaluated with an alternative negative control set.
         */
        NegativeSetVariantResponse: {
            /** Label */
            label: string;
            rankMetrics: components["schemas"]["RankMetricsResponse"];
            /**
             * Negativecount
             * @default 0
             */
            negativeCount: number;
        };
        /**
         * OpenStrategyRequest
         * @description Request to open a strategy.
         */
        OpenStrategyRequest: {
            /** Strategyid */
            strategyId?: string | null;
            /** Wdkstrategyid */
            wdkStrategyId?: number | null;
            /** Siteid */
            siteId?: string | null;
        };
        /**
         * OpenStrategyResponse
         * @description Open strategy response.
         */
        OpenStrategyResponse: {
            /**
             * Strategyid
             * Format: uuid
             */
            strategyId: string;
        };
        /**
         * OperatorComparisonResponse
         * @description Comparison of operators at a single combine node.
         */
        OperatorComparisonResponse: {
            /** Combinenodeid */
            combineNodeId: string;
            /** Currentoperator */
            currentOperator: string;
            /** Variants */
            variants?: components["schemas"]["OperatorVariantResponse"][];
            /**
             * Recommendation
             * @default
             */
            recommendation: string;
            /**
             * Recommendedoperator
             * @default
             */
            recommendedOperator: string;
            /** Precisionatkdelta */
            precisionAtKDelta?: {
                [key: string]: number;
            };
        };
        /**
         * OperatorKnobRequest
         * @description A boolean-operator knob for tree optimization.
         */
        OperatorKnobRequest: {
            /** Combinenodeid */
            combineNodeId: string;
            /** Options */
            options?: string[];
        };
        /**
         * OperatorKnobResponse
         * @description A combine-node operator that can be switched during optimization.
         */
        OperatorKnobResponse: {
            /** Combinenodeid */
            combineNodeId: string;
            /** Options */
            options?: string[];
        };
        /**
         * OperatorVariantResponse
         * @description Metrics for one boolean operator at a combine node.
         */
        OperatorVariantResponse: {
            /** Operator */
            operator: string;
            /** Positivehits */
            positiveHits: number;
            /** Negativehits */
            negativeHits: number;
            /** Totalresults */
            totalResults: number;
            /** Recall */
            recall: number;
            /** Falsepositiverate */
            falsePositiveRate: number;
            /** F1Score */
            f1Score: number;
        };
        /**
         * OptimizationParameterSpecData
         * @description Specification for one optimization parameter.
         */
        OptimizationParameterSpecData: {
            /** Name */
            name: string;
            /** Type */
            type: string;
            /** Minvalue */
            minValue?: number | null;
            /** Maxvalue */
            maxValue?: number | null;
            /** Logscale */
            logScale?: boolean | null;
            /** Choices */
            choices?: string[] | null;
        };
        /**
         * OptimizationProgressEventData
         * @description Payload for ``optimization_progress`` SSE events.
         */
        OptimizationProgressEventData: {
            /** Optimizationid */
            optimizationId: string;
            /**
             * Status
             * @default
             */
            status: string;
            /** Searchname */
            searchName?: string | null;
            /** Recordtype */
            recordType?: string | null;
            /** Budget */
            budget?: number | null;
            /** Objective */
            objective?: string | null;
            /** Currenttrial */
            currentTrial?: number | null;
            /** Totaltrials */
            totalTrials?: number | null;
            /** Parameterspecs */
            parameterSpecs?: components["schemas"]["OptimizationParameterSpecData"][] | null;
            trial?: components["schemas"]["OptimizationTrialData"] | null;
            bestTrial?: components["schemas"]["OptimizationTrialData"] | null;
            /** Recenttrials */
            recentTrials?: components["schemas"]["OptimizationTrialData"][] | null;
            /** Alltrials */
            allTrials?: components["schemas"]["OptimizationTrialData"][] | null;
            /** Paretofrontier */
            paretoFrontier?: components["schemas"]["OptimizationTrialData"][] | null;
            /** Sensitivity */
            sensitivity?: {
                [key: string]: number;
            } | null;
            /** Totaltimeseconds */
            totalTimeSeconds?: number | null;
            /** Error */
            error?: string | null;
        };
        /**
         * OptimizationResultResponse
         * @description Complete optimization result.
         */
        OptimizationResultResponse: {
            /** Optimizationid */
            optimizationId: string;
            /** Status */
            status: string;
            bestTrial?: components["schemas"]["OptimizationTrialData"] | null;
            /** Alltrials */
            allTrials?: components["schemas"]["OptimizationTrialData"][];
            /** Paretofrontier */
            paretoFrontier?: components["schemas"]["OptimizationTrialData"][];
            /** Sensitivity */
            sensitivity?: {
                [key: string]: number;
            };
            /**
             * Totaltimeseconds
             * @default 0
             */
            totalTimeSeconds: number;
            /**
             * Totaltrials
             * @default 0
             */
            totalTrials: number;
        };
        /**
         * OptimizationSpecRequest
         * @description Describes a single parameter to optimise.
         */
        OptimizationSpecRequest: {
            /** Name */
            name: string;
            /**
             * Type
             * @enum {string}
             */
            type: "numeric" | "integer" | "categorical";
            /** Min */
            min?: number | null;
            /** Max */
            max?: number | null;
            /** Step */
            step?: number | null;
            /** Choices */
            choices?: string[] | null;
        };
        /**
         * OptimizationSpecResponse
         * @description Describes a single parameter to optimise.
         */
        OptimizationSpecResponse: {
            /** Name */
            name: string;
            /**
             * Type
             * @enum {string}
             */
            type: "numeric" | "integer" | "categorical";
            /** Min */
            min?: number | null;
            /** Max */
            max?: number | null;
            /** Step */
            step?: number | null;
            /** Choices */
            choices?: string[] | null;
        };
        /**
         * OptimizationTrialData
         * @description A single optimization trial result.
         */
        OptimizationTrialData: {
            /** Trialnumber */
            trialNumber: number;
            /** Parameters */
            parameters?: {
                [key: string]: components["schemas"]["JSONValue"];
            };
            /**
             * Score
             * @default 0
             */
            score: number;
            /** Recall */
            recall?: number | null;
            /** Falsepositiverate */
            falsePositiveRate?: number | null;
            /** Estimatedsize */
            estimatedSize?: number | null;
            /** Positivehits */
            positiveHits?: number | null;
            /** Negativehits */
            negativeHits?: number | null;
            /** Totalpositives */
            totalPositives?: number | null;
            /** Totalnegatives */
            totalNegatives?: number | null;
        };
        /**
         * OrganismsResponse
         * @description Available organisms for a site.
         */
        OrganismsResponse: {
            /** Organisms */
            organisms: string[];
        };
        /**
         * OverlapRequest
         * @description Request to compute pairwise gene set overlap between experiments.
         */
        OverlapRequest: {
            /** Experimentids */
            experimentIds: string[];
        };
        /**
         * OverlapResult
         * @description Return shape of :func:`compute_gene_set_overlap`.
         */
        OverlapResult: {
            /** Experimentids */
            experimentIds: string[];
            /** Experimentlabels */
            experimentLabels: {
                [key: string]: string;
            };
            /** Pairwise */
            pairwise: components["schemas"]["PairwiseOverlap"][];
            /** Perexperiment */
            perExperiment: components["schemas"]["PerExperimentSummary"][];
            /** Universalgenes */
            universalGenes: string[];
            /** Totaluniquegenes */
            totalUniqueGenes: number;
            /** Genemembership */
            geneMembership: components["schemas"]["GeneMembership"][];
        };
        /**
         * PairwiseOverlap
         * @description Shape of one pairwise comparison entry.
         */
        PairwiseOverlap: {
            /** Experimenta */
            experimentA: string;
            /** Experimentb */
            experimentB: string;
            /** Labela */
            labelA: string;
            /** Labelb */
            labelB: string;
            /** Sizea */
            sizeA: number;
            /** Sizeb */
            sizeB: number;
            /** Intersection */
            intersection: number;
            /** Union */
            union: number;
            /** Jaccard */
            jaccard: number;
            /** Sharedgenes */
            sharedGenes: string[];
            /** Uniquea */
            uniqueA: string[];
            /** Uniqueb */
            uniqueB: string[];
        };
        /**
         * ParamSpecResponse
         * @description Normalized parameter spec (UI-friendly).
         */
        ParamSpecResponse: {
            /** Name */
            name: string;
            /** Displayname */
            displayName?: string | null;
            /** Type */
            type: string;
            /**
             * Allowemptyvalue
             * @default false
             */
            allowEmptyValue: boolean;
            /** Allowmultiplevalues */
            allowMultipleValues?: boolean | null;
            /** Multipick */
            multiPick?: boolean | null;
            /** Minselectedcount */
            minSelectedCount?: number | null;
            /** Maxselectedcount */
            maxSelectedCount?: number | null;
            /**
             * Countonlyleaves
             * @default false
             */
            countOnlyLeaves: boolean;
            initialDisplayValue?: components["schemas"]["JSONValue"] | null;
            vocabulary?: components["schemas"]["JSONValue"] | null;
            /** Min */
            min?: number | null;
            /** Max */
            max?: number | null;
            /**
             * Isnumber
             * @default false
             */
            isNumber: boolean;
            /** Increment */
            increment?: number | null;
            /** Displaytype */
            displayType?: string | null;
            /**
             * Isvisible
             * @default true
             */
            isVisible: boolean;
            /** Group */
            group?: string | null;
            /** Dependentparams */
            dependentParams?: string[];
            /** Help */
            help?: string | null;
        };
        /**
         * ParamSpecsRequest
         * @description Parameter specs request (optionally contextual).
         */
        ParamSpecsRequest: {
            contextValues?: components["schemas"]["JSONObject"];
        };
        /**
         * ParameterSensitivityResponse
         * @description Sensitivity sweep for one numeric parameter on one leaf step.
         */
        ParameterSensitivityResponse: {
            /** Stepid */
            stepId: string;
            /** Paramname */
            paramName: string;
            /** Currentvalue */
            currentValue: number;
            /** Sweeppoints */
            sweepPoints?: components["schemas"]["ParameterSweepPointResponse"][];
            /**
             * Recommendedvalue
             * @default 0
             */
            recommendedValue: number;
            /**
             * Recommendation
             * @default
             */
            recommendation: string;
        };
        /**
         * ParameterSweepPointResponse
         * @description One data point in a parameter sensitivity sweep.
         */
        ParameterSweepPointResponse: {
            /** Value */
            value: number;
            /** Positivehits */
            positiveHits: number;
            /** Negativehits */
            negativeHits: number;
            /** Totalresults */
            totalResults: number;
            /** Recall */
            recall: number;
            /** Fpr */
            fpr: number;
            /** F1 */
            f1: number;
        };
        /**
         * PatchExperimentRequest
         * @description Request body for PATCH /experiments/{experiment_id}.
         */
        PatchExperimentRequest: {
            /** Notes */
            notes?: string | null;
        };
        /**
         * PerExperimentSummary
         * @description Shape of one per-experiment summary entry.
         */
        PerExperimentSummary: {
            /** Experimentid */
            experimentId: string;
            /** Label */
            label: string;
            /** Totalgenes */
            totalGenes: number;
            /** Uniquegenes */
            uniqueGenes: number;
            /** Sharedgenes */
            sharedGenes: number;
        };
        /** PlanNormalizeRequest */
        PlanNormalizeRequest: {
            /** Siteid */
            siteId: string;
            plan: components["schemas"]["StrategyPlanPayload-Input"];
        };
        /** PlanNormalizeResponse */
        PlanNormalizeResponse: {
            plan: components["schemas"]["StrategyPlanPayload-Output"];
            warnings?: components["schemas"]["JSONArray"] | null;
        };
        /**
         * PlanStepNode
         * @description Untyped recursive strategy node.
         *
         *     Kind is inferred from structure:
         *     - combine: primary_input and secondary_input
         *     - transform: primary_input only
         *     - search: no inputs
         */
        "PlanStepNode-Input": {
            /** Searchname */
            searchName: string;
            parameters?: components["schemas"]["JSONObject"];
            primaryInput?: components["schemas"]["PlanStepNode-Input"] | null;
            secondaryInput?: components["schemas"]["PlanStepNode-Input"] | null;
            operator?: components["schemas"]["CombineOp"] | null;
            colocationParams?: components["schemas"]["ColocationParams"] | null;
            /** Displayname */
            displayName?: string | null;
            /** Filters */
            filters?: components["schemas"]["StepFilter"][];
            /** Analyses */
            analyses?: components["schemas"]["StepAnalysis-Input"][];
            /** Reports */
            reports?: components["schemas"]["StepReport-Input"][];
            /** Wdkweight */
            wdkWeight?: number | null;
            /** Id */
            id?: string;
        };
        /**
         * PlanStepNode
         * @description Untyped recursive strategy node.
         *
         *     Kind is inferred from structure:
         *     - combine: primary_input and secondary_input
         *     - transform: primary_input only
         *     - search: no inputs
         */
        "PlanStepNode-Output": {
            /** Searchname */
            searchName: string;
            parameters?: components["schemas"]["JSONObject"];
            primaryInput?: components["schemas"]["PlanStepNode-Output"] | null;
            secondaryInput?: components["schemas"]["PlanStepNode-Output"] | null;
            operator?: components["schemas"]["CombineOp"] | null;
            colocationParams?: components["schemas"]["ColocationParams"] | null;
            /** Displayname */
            displayName?: string | null;
            /** Filters */
            filters?: components["schemas"]["StepFilter"][];
            /** Analyses */
            analyses?: components["schemas"]["StepAnalysis-Output"][];
            /** Reports */
            reports?: components["schemas"]["StepReport-Output"][];
            /** Wdkweight */
            wdkWeight?: number | null;
            /** Id */
            id?: string;
        };
        /**
         * PlanningArtifactEventData
         * @description Payload for ``planning_artifact`` SSE events.
         */
        PlanningArtifactEventData: {
            planningArtifact?: components["schemas"]["PlanningArtifactResponse"] | null;
        };
        /**
         * PlanningArtifactResponse
         * @description Strategy planning artifact.
         */
        PlanningArtifactResponse: {
            /** Id */
            id: string;
            /** Title */
            title: string;
            /** Summarymarkdown */
            summaryMarkdown: string;
            /** Assumptions */
            assumptions?: string[];
            /** Parameters */
            parameters?: {
                [key: string]: components["schemas"]["JSONValue"];
            };
            proposedStrategyPlan?: components["schemas"]["JSONObject"] | null;
            /** Createdat */
            createdAt: string;
        };
        /**
         * PrimaryKeyPart
         * @description A single part of a composite WDK primary key.
         */
        PrimaryKeyPart: {
            /** Name */
            name: string;
            /** Value */
            value: string;
        };
        /**
         * ProviderStatus
         * @description Per-provider API-key availability.
         */
        ProviderStatus: {
            /** Openai */
            openai: boolean;
            /** Anthropic */
            anthropic: boolean;
            /** Google */
            google: boolean;
            /** Ollama */
            ollama: boolean;
        };
        /**
         * RankMetricsResponse
         * @description Rank-based evaluation metrics computed over an ordered result list.
         */
        RankMetricsResponse: {
            /** Precisionatk */
            precisionAtK?: {
                [key: string]: number;
            };
            /** Recallatk */
            recallAtK?: {
                [key: string]: number;
            };
            /** Enrichmentatk */
            enrichmentAtK?: {
                [key: string]: number;
            };
            /** Prcurve */
            prCurve?: [
                number,
                number
            ][];
            /** Listsizevsrecall */
            listSizeVsRecall?: [
                number,
                number
            ][];
            /**
             * Totalresults
             * @default 0
             */
            totalResults: number;
        };
        /**
         * ReasoningEventData
         * @description Payload for ``reasoning`` SSE events.
         */
        ReasoningEventData: {
            /** Reasoning */
            reasoning?: string | null;
        };
        /**
         * RecordDetailRequest
         * @description Request to fetch a single record by primary key.
         */
        RecordDetailRequest: {
            /** Primarykey */
            primaryKey: components["schemas"]["PrimaryKeyPart"][];
        };
        /**
         * RecordTypeResponse
         * @description Record type information.
         */
        RecordTypeResponse: {
            /** Name */
            name: string;
            /** Displayname */
            displayName: string;
            /** Description */
            description?: string | null;
        };
        /**
         * RefineRequest
         * @description Request to refine an experiment's strategy.
         */
        RefineRequest: {
            /**
             * Action
             * @enum {string}
             */
            action: "combine" | "transform";
            /**
             * Searchname
             * @default
             */
            searchName: string;
            parameters?: components["schemas"]["JSONObject"];
            /**
             * Operator
             * @default INTERSECT
             */
            operator: string;
            /**
             * Transformname
             * @default
             */
            transformName: string;
        };
        /**
         * ResolvedGeneResponse
         * @description A resolved gene record.
         */
        ResolvedGeneResponse: {
            /** Geneid */
            geneId: string;
            /**
             * Displayname
             * @default
             */
            displayName: string;
            /**
             * Organism
             * @default
             */
            organism: string;
            /**
             * Product
             * @default
             */
            product: string;
            /**
             * Genename
             * @default
             */
            geneName: string;
            /**
             * Genetype
             * @default
             */
            geneType: string;
            /**
             * Location
             * @default
             */
            location: string;
        };
        /**
         * ReverseSearchRequest
         * @description Rank user's gene sets by recall of given positive genes.
         */
        ReverseSearchRequest: {
            /** Positivegeneids */
            positiveGeneIds: string[];
            /** Negativegeneids */
            negativeGeneIds?: string[] | null;
            /** Siteid */
            siteId: string;
        };
        /**
         * ReverseSearchResultItem
         * @description A single ranked gene set in reverse search results.
         */
        ReverseSearchResultItem: {
            /** Genesetid */
            geneSetId: string;
            /** Name */
            name: string;
            /** Searchname */
            searchName?: string | null;
            /** Recall */
            recall: number;
            /** Precision */
            precision: number;
            /** F1 */
            f1: number;
            /** Estimatedsize */
            estimatedSize: number;
            /** Overlapcount */
            overlapCount: number;
        };
        /**
         * RunCrossValidationRequest
         * @description Request to run cross-validation on an existing experiment.
         */
        RunCrossValidationRequest: {
            /**
             * Kfolds
             * @default 5
             */
            kFolds: number;
        };
        /**
         * RunEnrichmentRequest
         * @description Request to run enrichment on an existing experiment.
         */
        RunEnrichmentRequest: {
            /** Enrichmenttypes */
            enrichmentTypes: ("go_function" | "go_component" | "go_process" | "pathway" | "word")[];
        };
        /**
         * SSESchemaIndex
         * @description Index of all SSE event data schemas. Never called -- exists for OpenAPI generation.
         */
        SSESchemaIndex: {
            message_start?: components["schemas"]["MessageStartEventData"] | null;
            user_message?: components["schemas"]["UserMessageEventData"] | null;
            assistant_delta?: components["schemas"]["AssistantDeltaEventData"] | null;
            assistant_message?: components["schemas"]["AssistantMessageEventData"] | null;
            tool_call_start?: components["schemas"]["ToolCallStartEventData"] | null;
            tool_call_end?: components["schemas"]["ToolCallEndEventData"] | null;
            subkani_task_start?: components["schemas"]["SubKaniTaskStartEventData"] | null;
            subkani_tool_call_start?: components["schemas"]["SubKaniToolCallStartEventData"] | null;
            subkani_tool_call_end?: components["schemas"]["SubKaniToolCallEndEventData"] | null;
            subkani_task_end?: components["schemas"]["SubKaniTaskEndEventData"] | null;
            token_usage_partial?: components["schemas"]["TokenUsagePartialEventData"] | null;
            model_selected?: components["schemas"]["ModelSelectedEventData"] | null;
            optimization_progress?: components["schemas"]["OptimizationProgressEventData"] | null;
            optimization_trial?: components["schemas"]["OptimizationTrialData"] | null;
            optimization_parameter_spec?: components["schemas"]["OptimizationParameterSpecData"] | null;
            error?: components["schemas"]["ErrorEventData"] | null;
            graph_snapshot?: components["schemas"]["GraphSnapshotEventData"] | null;
            strategy_meta?: components["schemas"]["StrategyMetaEventData"] | null;
            graph_plan?: components["schemas"]["GraphPlanEventData"] | null;
            strategy_update?: components["schemas"]["StrategyUpdateEventData"] | null;
            strategy_link?: components["schemas"]["StrategyLinkEventData"] | null;
            graph_cleared?: components["schemas"]["GraphClearedEventData"] | null;
            executor_build_request?: components["schemas"]["ExecutorBuildRequestEventData"] | null;
            gene_set_summary?: components["schemas"]["GeneSetSummary"] | null;
            workbench_gene_set?: components["schemas"]["WorkbenchGeneSetEventData"] | null;
            citations?: components["schemas"]["CitationsEventData"] | null;
            planning_artifact?: components["schemas"]["PlanningArtifactEventData"] | null;
            reasoning?: components["schemas"]["ReasoningEventData"] | null;
            message_end?: components["schemas"]["MessageEndEventData"] | null;
        };
        /**
         * SearchResponse
         * @description Search information.
         */
        SearchResponse: {
            /** Name */
            name: string;
            /** Displayname */
            displayName: string;
            /** Description */
            description?: string | null;
            /** Recordtype */
            recordType: string;
        };
        /** SearchValidationErrors */
        SearchValidationErrors: {
            /** General */
            general?: string[];
            /** Bykey */
            byKey?: {
                [key: string]: string[];
            };
        };
        /** SearchValidationPayload */
        SearchValidationPayload: {
            /** Isvalid */
            isValid: boolean;
            normalizedContextValues?: components["schemas"]["JSONObject"];
            errors?: components["schemas"]["SearchValidationErrors"];
        };
        /**
         * SearchValidationRequest
         * @description Search parameter validation request.
         */
        SearchValidationRequest: {
            contextValues?: components["schemas"]["JSONObject"];
        };
        /**
         * SearchValidationResponse
         * @description Stable validation response for UI consumption.
         */
        SearchValidationResponse: {
            validation: components["schemas"]["SearchValidationPayload"];
        };
        /**
         * SetOperationRequest
         * @description Perform set operations between two gene sets.
         */
        SetOperationRequest: {
            /** Setaid */
            setAId: string;
            /** Setbid */
            setBId: string;
            /**
             * Operation
             * @enum {string}
             */
            operation: "intersect" | "union" | "minus";
            /** Name */
            name: string;
        };
        /**
         * SiteResponse
         * @description VEuPathDB site information.
         */
        SiteResponse: {
            /** Id */
            id: string;
            /** Name */
            name: string;
            /** Displayname */
            displayName: string;
            /** Baseurl */
            baseUrl: string;
            /** Projectid */
            projectId: string;
            /** Isportal */
            isPortal: boolean;
        };
        /**
         * StepAnalysis
         * @description Analysis configuration for a step.
         *
         *     WDK fields: analysisType (str), parameters (JSONObject), customName (str|null).
         */
        "StepAnalysis-Input": {
            /** Analysistype */
            analysisType: string;
            parameters?: components["schemas"]["JSONObject"];
            /** Customname */
            customName?: string | null;
        };
        /**
         * StepAnalysis
         * @description Analysis configuration for a step.
         *
         *     WDK fields: analysisType (str), parameters (JSONObject), customName (str|null).
         */
        "StepAnalysis-Output": {
            /** Analysistype */
            analysisType: string;
            parameters?: components["schemas"]["JSONObject"];
            /** Customname */
            customName?: string | null;
        };
        /**
         * StepAnalysisProgressDataResponse
         * @description Progress data for step analysis.
         */
        StepAnalysisProgressDataResponse: {
            /** Phase */
            phase: string;
            /** Currentstep */
            currentStep?: number | null;
            /** Totalsteps */
            totalSteps?: number | null;
            /** Stepid */
            stepId?: string | null;
            /** Searchname */
            searchName?: string | null;
            /** Message */
            message?: string | null;
        };
        /**
         * StepAnalysisResultResponse
         * @description Container for all deterministic step analysis results.
         */
        StepAnalysisResultResponse: {
            /** Stepevaluations */
            stepEvaluations?: components["schemas"]["StepEvaluationResponse"][];
            /** Operatorcomparisons */
            operatorComparisons?: components["schemas"]["OperatorComparisonResponse"][];
            /** Stepcontributions */
            stepContributions?: components["schemas"]["StepContributionResponse"][];
            /** Parametersensitivities */
            parameterSensitivities?: components["schemas"]["ParameterSensitivityResponse"][];
        };
        /**
         * StepContributionResponse
         * @description Ablation analysis for one leaf step.
         */
        StepContributionResponse: {
            /** Stepid */
            stepId: string;
            /** Searchname */
            searchName: string;
            /** Baselinerecall */
            baselineRecall: number;
            /** Ablatedrecall */
            ablatedRecall: number;
            /** Recalldelta */
            recallDelta: number;
            /** Baselinefpr */
            baselineFpr: number;
            /** Ablatedfpr */
            ablatedFpr: number;
            /** Fprdelta */
            fprDelta: number;
            /**
             * Verdict
             * @enum {string}
             */
            verdict: "essential" | "helpful" | "neutral" | "harmful";
            /**
             * Enrichmentdelta
             * @default 0
             */
            enrichmentDelta: number;
            /**
             * Narrative
             * @default
             */
            narrative: string;
        };
        /**
         * StepCountsRequest
         * @description Request to compute step counts from a plan.
         */
        StepCountsRequest: {
            /** Siteid */
            siteId: string;
            plan: components["schemas"]["StrategyPlanPayload-Input"];
        };
        /**
         * StepCountsResponse
         * @description Step counts keyed by local step ID.
         */
        StepCountsResponse: {
            /** Counts */
            counts: {
                [key: string]: number | null;
            };
        };
        /**
         * StepEvaluationResponse
         * @description Per-leaf-step evaluation against controls.
         */
        StepEvaluationResponse: {
            /** Stepid */
            stepId: string;
            /** Searchname */
            searchName: string;
            /** Displayname */
            displayName: string;
            /** Estimatedsize */
            estimatedSize: number;
            /** Positivehits */
            positiveHits: number;
            /** Positivetotal */
            positiveTotal: number;
            /** Negativehits */
            negativeHits: number;
            /** Negativetotal */
            negativeTotal: number;
            /** Recall */
            recall: number;
            /** Falsepositiverate */
            falsePositiveRate: number;
            /** Capturedpositiveids */
            capturedPositiveIds?: string[];
            /** Capturednegativeids */
            capturedNegativeIds?: string[];
            /**
             * Tpmovement
             * @default 0
             */
            tpMovement: number;
            /**
             * Fpmovement
             * @default 0
             */
            fpMovement: number;
            /**
             * Fnmovement
             * @default 0
             */
            fnMovement: number;
        };
        /**
         * StepFilter
         * @description Filter applied to a step's result.
         *
         *     WDK FilterValueArray element: { name: string, value: any, disabled?: boolean }.
         */
        StepFilter: {
            /** Name */
            name: string;
            value?: components["schemas"]["JSONValue"];
            /**
             * Disabled
             * @default false
             */
            disabled: boolean;
        };
        /**
         * StepReport
         * @description Report request attached to a step.
         *
         *     WDK fields: reportName (str, default "standard"), config (JSONObject).
         */
        "StepReport-Input": {
            /**
             * Reportname
             * @default standard
             */
            reportName: string;
            config?: components["schemas"]["JSONObject"];
        };
        /**
         * StepReport
         * @description Report request attached to a step.
         *
         *     WDK fields: reportName (str, default "standard"), config (JSONObject).
         */
        "StepReport-Output": {
            /**
             * Reportname
             * @default standard
             */
            reportName: string;
            config?: components["schemas"]["JSONObject"];
        };
        /**
         * StepResponse
         * @description Strategy step — WDK-aligned fields.
         */
        StepResponse: {
            /** Id */
            id: string;
            /** Kind */
            kind?: string | null;
            /** Displayname */
            displayName?: string | null;
            /** Searchname */
            searchName?: string | null;
            /** Recordtype */
            recordType?: string | null;
            parameters?: components["schemas"]["JSONObject"] | null;
            /** Operator */
            operator?: string | null;
            colocationParams?: components["schemas"]["ColocationParams"] | null;
            /** Primaryinputstepid */
            primaryInputStepId?: string | null;
            /** Secondaryinputstepid */
            secondaryInputStepId?: string | null;
            /** Estimatedsize */
            estimatedSize?: number | null;
            /** Wdkstepid */
            wdkStepId?: number | null;
            /**
             * Isbuilt
             * @default false
             */
            isBuilt: boolean;
            /**
             * Isfiltered
             * @default false
             */
            isFiltered: boolean;
            validation?: components["schemas"]["WDKValidation"] | null;
            /** Filters */
            filters?: components["schemas"]["StepFilter"][] | null;
            /** Analyses */
            analyses?: components["schemas"]["StepAnalysis-Output"][] | null;
            /** Reports */
            reports?: components["schemas"]["StepReport-Output"][] | null;
        };
        /**
         * StrategyLinkEventData
         * @description Payload for ``strategy_link`` SSE events.
         */
        StrategyLinkEventData: {
            /** Graphid */
            graphId?: string | null;
            /** Wdkstrategyid */
            wdkStrategyId?: number | null;
            /** Wdkurl */
            wdkUrl?: string | null;
            /** Name */
            name?: string | null;
            /** Description */
            description?: string | null;
            /** Issaved */
            isSaved?: boolean | null;
        };
        /**
         * StrategyMetaEventData
         * @description Payload for ``strategy_meta`` SSE events.
         */
        StrategyMetaEventData: {
            /** Graphid */
            graphId?: string | null;
            /** Graphname */
            graphName?: string | null;
            /** Name */
            name?: string | null;
            /** Description */
            description?: string | null;
            /** Recordtype */
            recordType?: string | null;
        };
        /**
         * StrategyPlanPayload
         * @description Wire format for strategy plans (API request/response).
         *
         *     Wire format for strategy plans shared between API request/response and persistence.
         */
        "StrategyPlanPayload-Input": {
            /** Recordtype */
            recordType: string;
            root: components["schemas"]["PlanStepNode-Input"];
            /** Name */
            name?: string | null;
            /** Description */
            description?: string | null;
            metadata?: components["schemas"]["JSONObject"] | null;
            /** Stepcounts */
            stepCounts?: {
                [key: string]: number;
            } | null;
            /** Wdkstepids */
            wdkStepIds?: {
                [key: string]: number;
            } | null;
            /** Stepvalidations */
            stepValidations?: {
                [key: string]: components["schemas"]["WDKValidation"];
            } | null;
        };
        /**
         * StrategyPlanPayload
         * @description Wire format for strategy plans (API request/response).
         *
         *     Wire format for strategy plans shared between API request/response and persistence.
         */
        "StrategyPlanPayload-Output": {
            /** Recordtype */
            recordType: string;
            root: components["schemas"]["PlanStepNode-Output"];
            /** Name */
            name?: string | null;
            /** Description */
            description?: string | null;
            metadata?: components["schemas"]["JSONObject"] | null;
            /** Stepcounts */
            stepCounts?: {
                [key: string]: number;
            } | null;
            /** Wdkstepids */
            wdkStepIds?: {
                [key: string]: number;
            } | null;
            /** Stepvalidations */
            stepValidations?: {
                [key: string]: components["schemas"]["WDKValidation"];
            } | null;
        };
        /**
         * StrategyResponse
         * @description Unified strategy response — used for both list and detail views.
         *
         *     List views: ``steps`` is ``[]``, ``stepCount``/``estimatedSize`` are populated.
         *     Detail views: ``steps`` is populated, summary fields may also be set.
         */
        StrategyResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Title */
            title?: string | null;
            /** Description */
            description?: string | null;
            /** Siteid */
            siteId: string;
            /** Recordtype */
            recordType: string | null;
            /** Steps */
            steps?: components["schemas"]["StepResponse"][];
            /** Rootstepid */
            rootStepId?: string | null;
            /** Wdkstrategyid */
            wdkStrategyId?: number | null;
            /**
             * Issaved
             * @default false
             */
            isSaved: boolean;
            /** Messages */
            messages?: components["schemas"]["MessageResponse"][] | null;
            thinking?: components["schemas"]["ThinkingResponse"] | null;
            /** Modelid */
            modelId?: string | null;
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /**
             * Updatedat
             * Format: date-time
             */
            updatedAt: string;
            /** Stepcount */
            stepCount?: number | null;
            /** Estimatedsize */
            estimatedSize?: number | null;
            /** Wdkurl */
            wdkUrl?: string | null;
            /** Genesetid */
            geneSetId?: string | null;
            /** Dismissedat */
            dismissedAt?: string | null;
        };
        /**
         * StrategyUpdateEventData
         * @description Payload for ``strategy_update`` SSE events.
         */
        StrategyUpdateEventData: {
            /** Graphid */
            graphId?: string | null;
            step?: components["schemas"]["JSONObject"] | null;
            /** Allsteps */
            allSteps?: components["schemas"]["StepResponse"][];
        };
        /**
         * SubKaniActivityResponse
         * @description Sub-kani tool call activity.
         */
        SubKaniActivityResponse: {
            /** Calls */
            calls: {
                [key: string]: components["schemas"]["ToolCallResponse"][];
            };
            /** Status */
            status: {
                [key: string]: string;
            };
            /** Models */
            models?: {
                [key: string]: string;
            } | null;
            /** Tokenusage */
            tokenUsage?: {
                [key: string]: components["schemas"]["SubKaniTokenUsageResponse"];
            } | null;
        };
        /**
         * SubKaniTaskEndEventData
         * @description Payload for ``subkani_task_end`` SSE events.
         */
        SubKaniTaskEndEventData: {
            /** Task */
            task?: string | null;
            /** Status */
            status?: string | null;
            /** Modelid */
            modelId?: string | null;
            /** Prompttokens */
            promptTokens?: number | null;
            /** Completiontokens */
            completionTokens?: number | null;
            /** Llmcallcount */
            llmCallCount?: number | null;
            /** Estimatedcostusd */
            estimatedCostUsd?: number | null;
        };
        /**
         * SubKaniTaskStartEventData
         * @description Payload for ``subkani_task_start`` SSE events.
         */
        SubKaniTaskStartEventData: {
            /** Task */
            task?: string | null;
            /** Modelid */
            modelId?: string | null;
        };
        /**
         * SubKaniTokenUsageResponse
         * @description Token usage for a single sub-kani agent.
         */
        SubKaniTokenUsageResponse: {
            /** Prompttokens */
            promptTokens: number;
            /** Completiontokens */
            completionTokens: number;
            /**
             * Llmcallcount
             * @default 0
             */
            llmCallCount: number;
            /**
             * Estimatedcostusd
             * @default 0
             */
            estimatedCostUsd: number;
        };
        /**
         * SubKaniToolCallEndEventData
         * @description Payload for ``subkani_tool_call_end`` SSE events.
         */
        SubKaniToolCallEndEventData: {
            /** Id */
            id: string;
            /** Result */
            result?: string | null;
            /** Task */
            task?: string | null;
        };
        /**
         * SubKaniToolCallStartEventData
         * @description Payload for ``subkani_tool_call_start`` SSE events.
         */
        SubKaniToolCallStartEventData: {
            /** Id */
            id: string;
            /** Name */
            name: string;
            arguments?: components["schemas"]["JSONObject"];
            /** Task */
            task?: string | null;
        };
        /**
         * SystemConfigResponse
         * @description System configuration status (unauthenticated).
         */
        SystemConfigResponse: {
            /** Chat Provider */
            chatProvider: string;
            /** Llm Configured */
            llmConfigured: boolean;
            providers: components["schemas"]["ProviderStatus"];
        };
        /**
         * ThinkingResponse
         * @description In-progress tool call state.
         */
        ThinkingResponse: {
            /** Toolcalls */
            toolCalls?: components["schemas"]["ToolCallResponse"][] | null;
            /** Lasttoolcalls */
            lastToolCalls?: components["schemas"]["ToolCallResponse"][] | null;
            /** Subkanicalls */
            subKaniCalls?: {
                [key: string]: components["schemas"]["ToolCallResponse"][];
            } | null;
            /** Subkanistatus */
            subKaniStatus?: {
                [key: string]: string;
            } | null;
            /** Reasoning */
            reasoning?: string | null;
            /** Updatedat */
            updatedAt?: string | null;
        };
        /**
         * ThresholdKnobRequest
         * @description A numeric parameter knob for tree optimization.
         */
        ThresholdKnobRequest: {
            /** Stepid */
            stepId: string;
            /** Paramname */
            paramName: string;
            /**
             * Minval
             * @default 0
             */
            minVal: number;
            /**
             * Maxval
             * @default 1
             */
            maxVal: number;
            /** Stepsize */
            stepSize?: number | null;
        };
        /**
         * ThresholdKnobResponse
         * @description A numeric parameter on a leaf step that can be tuned.
         */
        ThresholdKnobResponse: {
            /** Stepid */
            stepId: string;
            /** Paramname */
            paramName: string;
            /** Minval */
            minVal: number;
            /** Maxval */
            maxVal: number;
            /** Stepsize */
            stepSize?: number | null;
        };
        /**
         * ThresholdSweepRequest
         * @description Request to sweep a parameter across a range (numeric) or set of values (categorical).
         */
        ThresholdSweepRequest: {
            /** Parametername */
            parameterName: string;
            /**
             * Sweeptype
             * @default numeric
             * @enum {string}
             */
            sweepType: "numeric" | "categorical";
            /** Minvalue */
            minValue?: number | null;
            /** Maxvalue */
            maxValue?: number | null;
            /**
             * Steps
             * @default 10
             */
            steps: number;
            /** Values */
            values?: string[] | null;
        };
        /**
         * TokenUsagePartialEventData
         * @description Payload for ``token_usage_partial`` SSE events.
         */
        TokenUsagePartialEventData: {
            /** Prompttokens */
            promptTokens?: number | null;
            /** Registeredtoolcount */
            registeredToolCount?: number | null;
        };
        /**
         * TokenUsageResponse
         * @description Token usage statistics for a message turn.
         */
        TokenUsageResponse: {
            /** Prompttokens */
            promptTokens: number;
            /** Completiontokens */
            completionTokens: number;
            /** Totaltokens */
            totalTokens: number;
            /**
             * Cachedtokens
             * @default 0
             */
            cachedTokens: number;
            /** Toolcallcount */
            toolCallCount: number;
            /** Registeredtoolcount */
            registeredToolCount: number;
            /**
             * Llmcallcount
             * @default 0
             */
            llmCallCount: number;
            /**
             * Subkaniprompttokens
             * @default 0
             */
            subKaniPromptTokens: number;
            /**
             * Subkanicompletiontokens
             * @default 0
             */
            subKaniCompletionTokens: number;
            /**
             * Subkanicallcount
             * @default 0
             */
            subKaniCallCount: number;
            /**
             * Estimatedcostusd
             * @default 0
             */
            estimatedCostUsd: number;
            /**
             * Modelid
             * @default
             */
            modelId: string;
        };
        /**
         * ToolCallEndEventData
         * @description Payload for ``tool_call_end`` SSE events.
         */
        ToolCallEndEventData: {
            /** Id */
            id: string;
            /** Result */
            result?: string | null;
        };
        /**
         * ToolCallResponse
         * @description Tool call information.
         */
        ToolCallResponse: {
            /** Id */
            id: string;
            /** Name */
            name: string;
            arguments: components["schemas"]["JSONObject"];
            /** Result */
            result?: string | null;
        };
        /**
         * ToolCallStartEventData
         * @description Payload for ``tool_call_start`` SSE events.
         */
        ToolCallStartEventData: {
            /** Id */
            id: string;
            /** Name */
            name: string;
            arguments?: components["schemas"]["JSONObject"];
        };
        /** ToolListResponse */
        ToolListResponse: {
            /** Tools */
            tools: components["schemas"]["_ToolItem"][];
        };
        /**
         * TreeOptimizationResultResponse
         * @description Result of multi-step tree-knob optimization.
         */
        TreeOptimizationResultResponse: {
            bestTrial?: components["schemas"]["TreeOptimizationTrialResponse"] | null;
            /** Alltrials */
            allTrials?: components["schemas"]["TreeOptimizationTrialResponse"][];
            /**
             * Totaltimeseconds
             * @default 0
             */
            totalTimeSeconds: number;
            /**
             * Objective
             * @default
             */
            objective: string;
        };
        /**
         * TreeOptimizationTrialResponse
         * @description One trial during tree-knob optimization.
         */
        TreeOptimizationTrialResponse: {
            /** Trialnumber */
            trialNumber: number;
            /** Parameters */
            parameters?: {
                [key: string]: number | string;
            };
            /**
             * Score
             * @default 0
             */
            score: number;
            rankMetrics?: components["schemas"]["RankMetricsResponse"] | null;
            /**
             * Listsize
             * @default 0
             */
            listSize: number;
        };
        /**
         * TrialProgressDataResponse
         * @description Progress data for a single optimization trial.
         */
        TrialProgressDataResponse: {
            /** Trialnumber */
            trialNumber: number;
            /** Totaltrials */
            totalTrials: number;
            /** Status */
            status: string;
            /** Score */
            score?: number | null;
            /** Recall */
            recall?: number | null;
            /** Falsepositiverate */
            falsePositiveRate?: number | null;
            /** Estimatedsize */
            estimatedSize?: number | null;
            /** Parameters */
            parameters?: {
                [key: string]: components["schemas"]["JSONValue"];
            } | null;
        };
        /**
         * UpdateStrategyRequest
         * @description Request to update a strategy.
         */
        UpdateStrategyRequest: {
            /** Name */
            name?: string | null;
            plan?: components["schemas"]["StrategyPlanPayload-Input"] | null;
            /** Wdkstrategyid */
            wdkStrategyId?: number | null;
            /** Issaved */
            isSaved?: boolean | null;
        };
        /**
         * UserMessageEventData
         * @description Payload for ``user_message`` SSE events.
         */
        UserMessageEventData: {
            /** Messageid */
            messageId?: string | null;
            /** Content */
            content?: string | null;
        };
        /** ValidationError */
        ValidationError: {
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
            /** Input */
            input?: unknown;
            /** Context */
            ctx?: Record<string, never>;
        };
        /**
         * WDKValidation
         * @description Step/search/strategy validation state.
         */
        WDKValidation: {
            /**
             * Level
             * @default NONE
             */
            level: string;
            /**
             * Isvalid
             * @default true
             */
            isValid: boolean;
            errors?: components["schemas"]["WDKValidationErrors"] | null;
        };
        /**
         * WDKValidationErrors
         * @description Validation error details.
         */
        WDKValidationErrors: {
            /** General */
            general?: string[];
            /** Bykey */
            byKey?: {
                [key: string]: string[];
            };
        };
        /** WorkbenchChatRequest */
        WorkbenchChatRequest: {
            /** Message */
            message: string;
            /** Siteid */
            siteId: string;
            /** Provider */
            provider?: ("openai" | "anthropic" | "google" | "ollama" | "mock") | null;
            /** Model */
            model?: string | null;
            /** Reasoningeffort */
            reasoningEffort?: ("none" | "low" | "medium" | "high") | null;
        };
        /** WorkbenchChatResponse */
        WorkbenchChatResponse: {
            /** Operationid */
            operationId: string;
            /** Streamid */
            streamId: string;
        };
        /**
         * WorkbenchGeneSetEventData
         * @description Payload for ``workbench_gene_set`` SSE events.
         */
        WorkbenchGeneSetEventData: {
            geneSet?: components["schemas"]["GeneSetSummary"] | null;
        };
        /** _ToolItem */
        _ToolItem: {
            /** Name */
            name: string;
            /** Description */
            description: string;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
};

export type $defs = Record<string, never>;

export interface operations {
    health_check_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthResponse"];
                };
            };
        };
    };
    system_config_health_config_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SystemConfigResponse"];
                };
            };
        };
    };
    readiness_check_health_ready_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthResponse"];
                };
            };
        };
    };
    list_sites_api_v1_sites_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SiteResponse"][];
                };
            };
        };
    };
    get_record_types_api_v1_sites__siteId__record_types_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                siteId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RecordTypeResponse"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_searches_api_v1_sites__siteId__searches_get: {
        parameters: {
            query?: {
                recordType?: string | null;
            };
            header?: never;
            path: {
                siteId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SearchResponse"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    validate_search_params_api_v1_sites__siteId__searches__recordType___searchName__validate_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                siteId: string;
                recordType: string;
                searchName: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SearchValidationRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SearchValidationResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_param_specs_with_context_api_v1_sites__siteId__searches__recordType___searchName__param_specs_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                siteId: string;
                recordType: string;
                searchName: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ParamSpecsRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ParamSpecResponse"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_organisms_api_v1_sites__siteId__organisms_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                siteId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OrganismsResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    search_genes_api_v1_sites__siteId__genes_search_get: {
        parameters: {
            query?: {
                q?: string;
                organism?: string | null;
                limit?: number;
                offset?: number;
            };
            header?: never;
            path: {
                siteId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GeneSearchResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    resolve_genes_api_v1_sites__siteId__genes_resolve_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                siteId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GeneResolveRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GeneResolveResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_models_api_v1_models_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ModelListResponse"];
                };
            };
        };
    };
    list_tools_api_v1_tools_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ToolListResponse"];
                };
            };
        };
    };
    chat_api_v1_chat_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ChatRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_strategies_api_v1_strategies_get: {
        parameters: {
            query?: {
                siteId?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StrategyResponse"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_strategy_api_v1_strategies_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateStrategyRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StrategyResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_dismissed_strategies_api_v1_strategies_dismissed_get: {
        parameters: {
            query?: {
                siteId?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StrategyResponse"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_strategy_api_v1_strategies__strategyId__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                strategyId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StrategyResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_strategy_api_v1_strategies__strategyId__delete: {
        parameters: {
            query?: {
                deleteFromWdk?: boolean;
            };
            header?: never;
            path: {
                strategyId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_strategy_api_v1_strategies__strategyId__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                strategyId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UpdateStrategyRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StrategyResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_strategy_ast_api_v1_strategies__strategyId__ast_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                strategyId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JSONObject"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    restore_strategy_api_v1_strategies__strategyId__restore_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                strategyId: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StrategyResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    compute_step_counts_api_v1_strategies_step_counts_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StepCountsRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StepCountsResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    normalize_plan_api_v1_strategies_plan_normalize_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PlanNormalizeRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PlanNormalizeResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    open_strategy_api_v1_strategies_open_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["OpenStrategyRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OpenStrategyResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    sync_all_wdk_strategies_api_v1_strategies_sync_wdk_post: {
        parameters: {
            query: {
                siteId: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StrategyResponse"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_experiments_api_v1_experiments__get: {
        parameters: {
            query?: {
                siteId?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JSONObject"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_experiment_api_v1_experiments__post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateExperimentRequest"];
            };
        };
        responses: {
            /** @description Experiment launched as background task */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        operationId?: string;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_batch_experiment_api_v1_experiments_batch_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateBatchExperimentRequest"];
            };
        };
        responses: {
            /** @description Batch experiment launched as background task */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        operationId?: string;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_benchmark_api_v1_experiments_benchmark_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateBenchmarkRequest"];
            };
        };
        responses: {
            /** @description Benchmark suite launched as background task */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        operationId?: string;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    seed_strategies_api_v1_experiments_seed_post: {
        parameters: {
            query?: {
                site_id?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description SSE stream of seed strategy/control-set progress */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "text/event-stream": string;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    compute_overlap_api_v1_experiments_overlap_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["OverlapRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OverlapResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    compare_enrichment_api_v1_experiments_enrichment_compare_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EnrichmentCompareRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EnrichmentCompareResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    run_cv_api_v1_experiments__experiment_id__cross_validate_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                experiment_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RunCrossValidationRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JSONObject"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    run_enrichment_api_v1_experiments__experiment_id__enrich_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                experiment_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RunEnrichmentRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JSONObject"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    custom_enrichment_api_v1_experiments__experiment_id__custom_enrich_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                experiment_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CustomEnrichRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CustomEnrichmentResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    re_evaluate_experiment_api_v1_experiments__experiment_id__re_evaluate_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                experiment_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JSONObject"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    threshold_sweep_api_v1_experiments__experiment_id__threshold_sweep_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                experiment_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ThresholdSweepRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_experiment_report_api_v1_experiments__experiment_id__export_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                experiment_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_experiment_api_v1_experiments__experiment_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                experiment_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JSONObject"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_experiment_api_v1_experiments__experiment_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                experiment_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_experiment_api_v1_experiments__experiment_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                experiment_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PatchExperimentRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JSONObject"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_experiment_attributes_api_v1_experiments__experiment_id__results_attributes_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                experiment_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JSONObject"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_experiment_records_api_v1_experiments__experiment_id__results_records_get: {
        parameters: {
            query?: {
                offset?: number;
                limit?: number;
                sort?: string | null;
                dir?: "ASC" | "DESC";
                attributes?: string | null;
                filterAttribute?: string | null;
                filterValue?: string | null;
            };
            header?: never;
            path: {
                experiment_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JSONObject"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_experiment_record_detail_api_v1_experiments__experiment_id__results_record_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                experiment_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RecordDetailRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JSONObject"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_experiment_distribution_api_v1_experiments__experiment_id__results_distributions__attribute_name__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                attribute_name: string;
                experiment_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JSONObject"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    refine_experiment_api_v1_experiments__experiment_id__refine_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                experiment_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RefineRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JSONObject"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    workbench_chat_api_v1_experiments__experiment_id__chat_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                experiment_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WorkbenchChatRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WorkbenchChatResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_workbench_chat_messages_api_v1_experiments__experiment_id__chat_messages_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                experiment_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JSONObject"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_control_sets_api_v1_control_sets_get: {
        parameters: {
            query?: {
                siteId?: string | null;
                tags?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ControlSetResponse"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_control_set_api_v1_control_sets_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateControlSetRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ControlSetResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_control_set_api_v1_control_sets__control_set_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                control_set_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ControlSetResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_control_set_api_v1_control_sets__control_set_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                control_set_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    login_with_password_api_v1_veupathdb_auth_login_post: {
        parameters: {
            query?: {
                redirectTo?: string | null;
                siteId?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["LoginPayload"] | null;
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuthSuccessResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    logout_api_v1_veupathdb_auth_logout_post: {
        parameters: {
            query?: {
                siteId?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuthSuccessResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    refresh_internal_auth_api_v1_veupathdb_auth_refresh_post: {
        parameters: {
            query?: {
                siteId?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuthSuccessResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    auth_status_api_v1_veupathdb_auth_status_get: {
        parameters: {
            query?: {
                siteId?: string;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuthStatusResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    subscribe_api_v1_operations__operation_id__subscribe_get: {
        parameters: {
            query?: {
                /** @description Resume from this Redis entry ID (for reconnection). */
                lastEventId?: string | null;
            };
            header?: never;
            path: {
                operation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    cancel_api_v1_operations__operation_id__cancel_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                operation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JSONObject"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_active_api_v1_operations_active_get: {
        parameters: {
            query?: {
                /** @description Filter by stream/strategy ID. */
                streamId?: string | null;
                /** @description Filter by operation type (chat, experiment). */
                type?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JSONObject"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_gene_sets_api_v1_gene_sets_get: {
        parameters: {
            query?: {
                siteId?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GeneSetResponse"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_gene_set_api_v1_gene_sets_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateGeneSetRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GeneSetResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_gene_set_api_v1_gene_sets__gene_set_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                gene_set_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GeneSetResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_gene_set_api_v1_gene_sets__gene_set_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                gene_set_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: boolean;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_operations_api_v1_gene_sets_operations_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SetOperationRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GeneSetResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reverse_search_api_v1_gene_sets_reverse_search_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReverseSearchRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReverseSearchResultItem"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    ensemble_scoring_api_v1_gene_sets_ensemble_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EnsembleScoringRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EnsembleScore"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    enrich_gene_set_api_v1_gene_sets__gene_set_id__enrich_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                gene_set_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GeneSetEnrichRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JSONObject"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_gene_set_attributes_api_v1_gene_sets__gene_set_id__results_attributes_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                gene_set_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JSONObject"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_gene_set_records_api_v1_gene_sets__gene_set_id__results_records_get: {
        parameters: {
            query?: {
                offset?: number;
                limit?: number;
                sort?: string | null;
                dir?: "ASC" | "DESC";
                attributes?: string | null;
                filterAttribute?: string | null;
                filterValue?: string | null;
            };
            header?: never;
            path: {
                gene_set_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JSONObject"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_gene_set_distribution_api_v1_gene_sets__gene_set_id__results_distributions__attribute_name__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                gene_set_id: string;
                attribute_name: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JSONObject"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_gene_set_record_detail_api_v1_gene_sets__gene_set_id__results_record_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                gene_set_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RecordDetailRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JSONObject"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    gene_confidence_api_v1_gene_sets_confidence_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GeneConfidenceRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["GeneConfidenceScoreResponse"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    download_export_api_v1_exports__export_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                export_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    sse_schemas_api_v1_internal_sse_schemas_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SSESchemaIndex"];
                };
            };
        };
    };
    experiment_schemas_api_v1_internal_experiment_schemas_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExperimentSchemaIndex"];
                };
            };
        };
    };
    purge_user_data_endpoint_api_v1_user_data_delete: {
        parameters: {
            query?: {
                siteId?: string | null;
                deleteWdk?: boolean;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JSONObject"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    build_gold_strategy_endpoint_api_v1_eval_build_gold_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["BuildGoldRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["BuildGoldResponse"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_strategy_gene_ids_api_v1_eval_strategy_gene_ids_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FetchGeneIdsRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: unknown;
                    };
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
}
