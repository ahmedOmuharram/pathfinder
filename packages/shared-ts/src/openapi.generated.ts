/**
 * AUTO-GENERATED FILE — DO NOT EDIT.
 *
 * Source: packages/spec/openapi.yaml
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
         *     In production, this should check database and cache connectivity.
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
    "/api/v1/sites/{siteId}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Site
         * @description Get a single site by ID.
         */
        get: operations["get_site_api_v1_sites__siteId__get"];
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
         * @description Get searches available on a site.
         *
         *     Optionally filter by record type.
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
    "/api/v1/sites/{siteId}/searches/{recordType}/{searchName}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Search Details
         * @description Get detailed search configuration with parameters.
         */
        get: operations["get_search_details_api_v1_sites__siteId__searches__recordType___searchName__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sites/{siteId}/searches/{recordType}/{searchName}/dependent-params": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Get Dependent Params
         * @description Get dependent parameter vocabulary values.
         */
        post: operations["get_dependent_params_api_v1_sites__siteId__searches__recordType___searchName__dependent_params_post"];
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
        /**
         * Get Param Specs
         * @description Return normalized parameter specs for UI consumption.
         */
        get: operations["get_param_specs_api_v1_sites__siteId__searches__recordType___searchName__param_specs_get"];
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
         * @description Send a chat message and receive streaming response.
         *
         *     Returns a Server-Sent Events stream with response chunks.
         */
        post: operations["chat_api_v1_chat_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/plans": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Plans */
        get: operations["list_plans_api_v1_plans_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/plans/open": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Open Plan */
        post: operations["open_plan_api_v1_plans_open_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/plans/{planSessionId}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Plan */
        get: operations["get_plan_api_v1_plans__planSessionId__get"];
        put?: never;
        post?: never;
        /** Delete Plan */
        delete: operations["delete_plan_api_v1_plans__planSessionId__delete"];
        options?: never;
        head?: never;
        /** Update Plan */
        patch: operations["update_plan_api_v1_plans__planSessionId__patch"];
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
         * @description List user's saved strategies.
         */
        get: operations["list_strategies_api_v1_strategies_get"];
        put?: never;
        /**
         * Create Strategy
         * @description Create a new strategy.
         */
        post: operations["create_strategy_api_v1_strategies_post"];
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
         * @description Get a strategy by ID.
         */
        get: operations["get_strategy_api_v1_strategies__strategyId__get"];
        put?: never;
        post?: never;
        /**
         * Delete Strategy
         * @description Delete a strategy.
         */
        delete: operations["delete_strategy_api_v1_strategies__strategyId__delete"];
        options?: never;
        head?: never;
        /**
         * Update Strategy
         * @description Update a strategy.
         */
        patch: operations["update_strategy_api_v1_strategies__strategyId__patch"];
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
    "/api/v1/strategies/wdk": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Wdk Strategies
         * @description List strategies from VEuPathDB WDK.
         */
        get: operations["list_wdk_strategies_api_v1_strategies_wdk_get"];
        put?: never;
        post?: never;
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
         * @description Batch-sync all WDK strategies into the local DB and return the full list.
         *
         *     For each non-internal WDK strategy, fetches the full payload and upserts
         *     a local copy. Returns the complete list of local strategies for this site
         *     (including non-WDK drafts).
         */
        post: operations["sync_all_wdk_strategies_api_v1_strategies_sync_wdk_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/strategies/wdk/{wdkStrategyId}": {
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
         * Delete Wdk Strategy
         * @description Delete a strategy from VEuPathDB WDK.
         */
        delete: operations["delete_wdk_strategy_api_v1_strategies_wdk__wdkStrategyId__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/strategies/wdk/{wdkStrategyId}/import": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Import Wdk Strategy
         * @description Import a WDK strategy as a local snapshot.
         */
        post: operations["import_wdk_strategy_api_v1_strategies_wdk__wdkStrategyId__import_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/strategies/{strategyId}/sync-wdk": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Sync Strategy From Wdk
         * @description Sync local strategy snapshot from VEuPathDB WDK.
         */
        post: operations["sync_strategy_from_wdk_api_v1_strategies__strategyId__sync_wdk_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/strategies/{strategyId}/steps/{step_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Step
         * @description Get a step from a strategy.
         */
        get: operations["get_step_api_v1_strategies__strategyId__steps__step_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/strategies/{strategyId}/steps/{step_id}/filters": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Step Filters
         * @description List filters attached to a step.
         */
        get: operations["list_step_filters_api_v1_strategies__strategyId__steps__step_id__filters_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/strategies/{strategyId}/steps/{step_id}/filters/available": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Available Filters
         * @description List available filters for a step (WDK-backed).
         */
        get: operations["list_available_filters_api_v1_strategies__strategyId__steps__step_id__filters_available_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/strategies/{strategyId}/steps/{step_id}/filters/{filter_name}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Set Step Filter
         * @description Add or update a filter for a step.
         */
        put: operations["set_step_filter_api_v1_strategies__strategyId__steps__step_id__filters__filter_name__put"];
        post?: never;
        /**
         * Delete Step Filter
         * @description Remove a filter from a step.
         */
        delete: operations["delete_step_filter_api_v1_strategies__strategyId__steps__step_id__filters__filter_name__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/strategies/{strategyId}/steps/{step_id}/analysis-types": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Analysis Types
         * @description List available analysis types for a step.
         */
        get: operations["list_analysis_types_api_v1_strategies__strategyId__steps__step_id__analysis_types_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/strategies/{strategyId}/steps/{step_id}/analysis-types/{analysis_type}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Analysis Type
         * @description Get analysis form metadata for a step.
         */
        get: operations["get_analysis_type_api_v1_strategies__strategyId__steps__step_id__analysis_types__analysis_type__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/strategies/{strategyId}/steps/{step_id}/analyses": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Step Analyses
         * @description List analysis instances for a step.
         */
        get: operations["list_step_analyses_api_v1_strategies__strategyId__steps__step_id__analyses_get"];
        put?: never;
        /**
         * Run Step Analysis
         * @description Run a step analysis and attach it locally.
         */
        post: operations["run_step_analysis_api_v1_strategies__strategyId__steps__step_id__analyses_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/strategies/{strategyId}/steps/{step_id}/reports": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Run Step Report
         * @description Run a report and attach it locally.
         */
        post: operations["run_step_report_api_v1_strategies__strategyId__steps__step_id__reports_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/results/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Preview Results
         * @description Preview step results.
         *
         *     Returns a sample of records and total count for the specified step.
         *     The strategy must have been pushed to WDK first.
         */
        post: operations["preview_results_api_v1_results_preview_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/results/download": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Download Results
         * @description Get download URL for step results.
         *
         *     Creates a temporary result on VEuPathDB and returns a download URL.
         */
        post: operations["download_results_api_v1_results_download_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/experiments": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Experiments
         * @description List all experiments, optionally filtered by site.
         */
        get: operations["list_experiments_api_v1_experiments_get"];
        put?: never;
        /**
         * Create Experiment
         * @description Create and run an experiment with SSE progress streaming.
         */
        post: operations["create_experiment_api_v1_experiments_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/experiments/importable-strategies": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List Importable Strategies
         * @description List Pathfinder strategies available for import into experiments.
         */
        get: operations["list_importable_strategies_api_v1_experiments_importable_strategies_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/experiments/importable-strategies/{strategy_id}/details": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Strategy Details
         * @description Fetch full strategy step tree for import into the multi-step builder.
         *
         *     The WDK ``GET /strategies/{id}`` response includes:
         *     - ``stepTree``: recursive tree with only ``stepId`` / ``primaryInput`` / ``secondaryInput``
         *     - ``steps``: a **map** (object keyed by string step ID) of full step data
         *       including ``searchName``, ``searchConfig.parameters``, ``customName``, etc.
         *
         *     This endpoint flattens the steps map into an array and enriches the
         *     step tree so the frontend can display search names and parameters.
         */
        get: operations["get_strategy_details_api_v1_experiments_importable_strategies__strategy_id__details_get"];
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
         * @description Run the same search across multiple organisms with SSE progress.
         */
        post: operations["create_batch_experiment_api_v1_experiments_batch_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
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
         *
         *     Expects ``{"primaryKey": [{"name": "...", "value": "..."}, ...]}``
         *     (or ``primary_key``) matching the record type's primary key structure.
         *     If the client sends fewer PK parts than the record type requires (e.g. only
         *     ``source_id`` for gene), missing parts such as ``project_id`` are filled
         *     from the site so WDK accepts the request.
         */
        post: operations["get_experiment_record_detail_api_v1_experiments__experiment_id__results_record_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/experiments/{experiment_id}/strategy": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Experiment Strategy
         * @description Get the WDK strategy tree for an experiment.
         */
        get: operations["get_experiment_strategy_api_v1_experiments__experiment_id__strategy_get"];
        put?: never;
        post?: never;
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
         * @description Get distribution data for an attribute using filter summary.
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
    "/api/v1/experiments/{experiment_id}/analyses/types": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Experiment Analysis Types
         * @description List available WDK step analysis types for an experiment.
         */
        get: operations["get_experiment_analysis_types_api_v1_experiments__experiment_id__analyses_types_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/experiments/{experiment_id}/analyses/run": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Run Experiment Analysis
         * @description Create and run a WDK step analysis on the experiment's step.
         */
        post: operations["run_experiment_analysis_api_v1_experiments__experiment_id__analyses_run_post"];
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
         * @description Sweep a numeric parameter across a range and compute metrics at each point.
         */
        post: operations["threshold_sweep_api_v1_experiments__experiment_id__threshold_sweep_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/experiments/{experiment_id}/step-contributions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Step Contributions
         * @description Analyse per-step contribution to overall result for multi-step experiments.
         *
         *     Evaluates controls against each leaf step individually to show how much
         *     each step contributes to the final strategy result.
         */
        post: operations["step_contributions_api_v1_experiments__experiment_id__step_contributions_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/experiments/ai-assist": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Ai Assist
         * @description AI assistant for the experiment wizard.
         *
         *     Streams a response with tool-use activity (web/literature search, site
         *     catalog lookup, gene lookup) to help the user with the current wizard step.
         */
        post: operations["ai_assist_api_v1_experiments_ai_assist_post"];
        delete?: never;
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
    "/api/v1/veupathdb/auth/token": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Accept Token
         * @description Accept a VEuPathDB Authorization token and store it as a cookie.
         */
        post: operations["accept_token_api_v1_veupathdb_auth_token_post"];
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
};

export type webhooks = Record<string, never>;

export type components = {
    schemas: {
        /**
         * AiAssistRequest
         * @description Request for the experiment wizard AI assistant.
         */
        AiAssistRequest: {
            /** Siteid */
            siteId: string;
            /**
             * Step
             * @enum {string}
             */
            step: "search" | "parameters" | "controls" | "run" | "results" | "analysis";
            /** Message */
            message: string;
            context?: components["schemas"]["JSONObject"];
            history?: components["schemas"]["JSONArray"];
            /** Model */
            model?: string | null;
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
         * @description Success response, optionally carrying the internal auth token.
         */
        AuthSuccessResponse: {
            /** Success */
            success: boolean;
            /** Authtoken */
            authToken?: string | null;
        };
        /**
         * BatchOrganismTargetRequest
         * @description Per-organism override for a cross-organism batch experiment.
         */
        BatchOrganismTargetRequest: {
            /** Organism */
            organism: string;
            /** Positivecontrols */
            positiveControls?: string[];
            /** Negativecontrols */
            negativeControls?: string[];
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
            /** Plansessionid */
            planSessionId?: string | null;
            /** Siteid */
            siteId: string;
            /** Message */
            message: string;
            /**
             * Mode
             * @default execute
             * @enum {string}
             */
            mode: "execute" | "plan";
            /** Provider */
            provider?: ("openai" | "anthropic" | "google") | null;
            /** Model */
            model?: string | null;
            /** Reasoningeffort */
            reasoningEffort?: ("none" | "low" | "medium" | "high") | null;
            /** Referencestrategyid */
            referenceStrategyId?: string | null;
            /** Mentions */
            mentions?: components["schemas"]["ChatMention"][];
        };
        /** ColocationParams */
        ColocationParams: {
            /** Upstream */
            upstream: number;
            /** Downstream */
            downstream: number;
            /**
             * Strand
             * @default both
             */
            strand: string;
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
             */
            controlsValueFormat: string;
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
            optimizationObjective?: ("f1" | "recall" | "precision" | "specificity" | "balanced_accuracy" | "mcc" | "youdens_j" | "f_beta") | null;
            parameterDisplayValues?: components["schemas"]["JSONObject"] | null;
            /**
             * Enabletreeoptimization
             * @default false
             */
            enableTreeOptimization: boolean;
            /**
             * Treeoptimizationbudget
             * @default 20
             */
            treeOptimizationBudget: number;
            /**
             * Optimizeoperators
             * @default true
             */
            optimizeOperators: boolean;
            /**
             * Optimizeorthologs
             * @default false
             */
            optimizeOrthologs: boolean;
            /** Orthologorganisms */
            orthologOrganisms?: string[] | null;
            /**
             * Optimizestructure
             * @default false
             */
            optimizeStructure: boolean;
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
            plan: components["schemas"]["StrategyPlan-Input"];
        };
        /**
         * DependentParamsRequest
         * @description Dependent parameter values request.
         */
        DependentParamsRequest: {
            /** Parametername */
            parameterName: string;
            contextValues?: components["schemas"]["JSONObject"];
        };
        /**
         * DependentParamsResponse
         * @description Dependent parameter values response.
         */
        DependentParamsResponse: components["schemas"]["JSONArray"];
        /**
         * DownloadRequest
         * @description Request to download results.
         */
        DownloadRequest: {
            /**
             * Strategyid
             * Format: uuid
             */
            strategyId: string;
            /** Stepid */
            stepId: string;
            /**
             * Format
             * @default csv
             */
            format: string;
            /** Attributes */
            attributes?: string[] | null;
        };
        /**
         * DownloadResponse
         * @description Download response with URL.
         */
        DownloadResponse: {
            /** Downloadurl */
            downloadUrl: string;
            /**
             * Expiresat
             * Format: date-time
             */
            expiresAt: string;
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
         * MessageResponse
         * @description Chat message.
         */
        MessageResponse: {
            /** Role */
            role: string;
            /** Content */
            content: string;
            /** Toolcalls */
            toolCalls?: components["schemas"]["ToolCallResponse"][] | null;
            subKaniActivity?: components["schemas"]["SubKaniActivityResponse"] | null;
            /** Mode */
            mode?: ("execute" | "plan") | null;
            citations?: components["schemas"]["JSONArray"] | null;
            planningArtifacts?: components["schemas"]["JSONArray"] | null;
            /** Reasoning */
            reasoning?: string | null;
            optimizationProgress?: components["schemas"]["JSONObject"] | null;
            /**
             * Timestamp
             * Format: date-time
             */
            timestamp: string;
        };
        /** OpenPlanSessionRequest */
        OpenPlanSessionRequest: {
            /** Plansessionid */
            planSessionId?: string | null;
            /** Siteid */
            siteId: string;
            /** Title */
            title?: string | null;
        };
        /** OpenPlanSessionResponse */
        OpenPlanSessionResponse: {
            /**
             * Plansessionid
             * Format: uuid
             */
            planSessionId: string;
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
            /** Minvalue */
            minValue?: number | null;
            /** Maxvalue */
            maxValue?: number | null;
            /**
             * Isnumber
             * @default false
             */
            isNumber: boolean;
            /** Increment */
            increment?: number | null;
        };
        /**
         * ParamSpecsRequest
         * @description Parameter specs request (optionally contextual).
         */
        ParamSpecsRequest: {
            contextValues?: components["schemas"]["JSONObject"];
        };
        /** PlanMetadata */
        PlanMetadata: {
            /** Name */
            name?: string | null;
            /** Description */
            description?: string | null;
            /** Siteid */
            siteId?: string | null;
            /** Createdat */
            createdAt?: string | null;
        };
        /**
         * PlanNode
         * @description Untyped recursive plan node (WDK-aligned).
         *
         *     Kind is inferred from structure:
         *     - combine: primaryInput + secondaryInput
         *     - transform: primaryInput only
         *     - search: no inputs
         */
        "PlanNode-Input": {
            /** Id */
            id?: string | null;
            /** Displayname */
            displayName?: string | null;
            /** Filters */
            filters?: components["schemas"]["StepFilterSpec"][] | null;
            /** Analyses */
            analyses?: components["schemas"]["StepAnalysisSpec-Input"][] | null;
            /** Reports */
            reports?: components["schemas"]["StepReportSpec-Input"][] | null;
            /** Searchname */
            searchName: string;
            parameters?: components["schemas"]["JSONObject"];
            primaryInput?: components["schemas"]["PlanNode-Input"] | null;
            secondaryInput?: components["schemas"]["PlanNode-Input"] | null;
            /** Operator */
            operator?: string | null;
            colocationParams?: components["schemas"]["ColocationParams"] | null;
        } & {
            [key: string]: unknown;
        };
        /**
         * PlanNode
         * @description Untyped recursive plan node (WDK-aligned).
         *
         *     Kind is inferred from structure:
         *     - combine: primaryInput + secondaryInput
         *     - transform: primaryInput only
         *     - search: no inputs
         */
        "PlanNode-Output": {
            /** Id */
            id?: string | null;
            /** Displayname */
            displayName?: string | null;
            /** Filters */
            filters?: components["schemas"]["StepFilterSpec"][] | null;
            /** Analyses */
            analyses?: components["schemas"]["StepAnalysisSpec-Output"][] | null;
            /** Reports */
            reports?: components["schemas"]["StepReportSpec-Output"][] | null;
            /** Searchname */
            searchName: string;
            parameters?: components["schemas"]["JSONObject"];
            primaryInput?: components["schemas"]["PlanNode-Output"] | null;
            secondaryInput?: components["schemas"]["PlanNode-Output"] | null;
            /** Operator */
            operator?: string | null;
            colocationParams?: components["schemas"]["ColocationParams"] | null;
        } & {
            [key: string]: unknown;
        };
        /** PlanNormalizeRequest */
        PlanNormalizeRequest: {
            /** Siteid */
            siteId: string;
            plan: components["schemas"]["StrategyPlan-Input"];
        };
        /** PlanNormalizeResponse */
        PlanNormalizeResponse: {
            plan: components["schemas"]["StrategyPlan-Output"];
            warnings?: components["schemas"]["JSONArray"] | null;
        };
        /** PlanSessionResponse */
        PlanSessionResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Siteid */
            siteId: string;
            /** Title */
            title: string;
            /** Messages */
            messages?: components["schemas"]["MessageResponse"][] | null;
            thinking?: components["schemas"]["ThinkingResponse"] | null;
            planningArtifacts?: components["schemas"]["JSONArray"] | null;
            /** Modelid */
            modelId?: string | null;
            /**
             * Updatedat
             * Format: date-time
             */
            updatedAt: string;
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
        };
        /** PlanSessionSummaryResponse */
        PlanSessionSummaryResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Siteid */
            siteId: string;
            /** Title */
            title: string;
            /**
             * Updatedat
             * Format: date-time
             */
            updatedAt: string;
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
        };
        /**
         * PreviewRequest
         * @description Request to preview results.
         */
        PreviewRequest: {
            /**
             * Strategyid
             * Format: uuid
             */
            strategyId: string;
            /** Stepid */
            stepId: string;
            /**
             * Limit
             * @default 100
             */
            limit: number;
        };
        /**
         * PreviewResponse
         * @description Preview results response.
         */
        PreviewResponse: {
            /** Totalcount */
            totalCount: number;
            records: components["schemas"]["JSONArray"];
            /** Columns */
            columns: string[];
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
         * SearchDetailsResponse
         * @description Search details payload (UI-facing).
         */
        SearchDetailsResponse: {
            searchData?: components["schemas"]["JSONObject"] | null;
            validation?: components["schemas"]["JSONObject"] | null;
            searchConfig?: components["schemas"]["JSONObject"] | null;
            parameters?: components["schemas"]["JSONArray"] | null;
            paramMap?: components["schemas"]["JSONObject"] | null;
            question?: components["schemas"]["JSONObject"] | null;
        } & {
            [key: string]: unknown;
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
         * StepAnalysisRequest
         * @description Request to run a step analysis.
         */
        StepAnalysisRequest: {
            /** Analysistype */
            analysisType: string;
            parameters?: components["schemas"]["JSONObject"];
            /** Customname */
            customName?: string | null;
        };
        /**
         * StepAnalysisResponse
         * @description Analysis configuration attached to a step.
         */
        StepAnalysisResponse: {
            /** Analysistype */
            analysisType: string;
            parameters?: components["schemas"]["JSONObject"];
            /** Customname */
            customName?: string | null;
        };
        /**
         * StepAnalysisRunResponse
         * @description Result of running a step analysis.
         */
        StepAnalysisRunResponse: {
            analysis: components["schemas"]["StepAnalysisResponse"];
            wdk?: components["schemas"]["JSONObject"] | null;
        };
        /** StepAnalysisSpec */
        "StepAnalysisSpec-Input": {
            /** Analysistype */
            analysisType: string;
            parameters?: components["schemas"]["JSONObject"];
            /** Customname */
            customName?: string | null;
        };
        /** StepAnalysisSpec */
        "StepAnalysisSpec-Output": {
            /** Analysistype */
            analysisType: string;
            parameters?: components["schemas"]["JSONObject"];
            /** Customname */
            customName?: string | null;
        };
        /**
         * StepCountsRequest
         * @description Request to compute step counts from a plan.
         */
        StepCountsRequest: {
            /** Siteid */
            siteId: string;
            plan: components["schemas"]["StrategyPlan-Input"];
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
         * StepFilterRequest
         * @description Request to set or update a step filter.
         */
        StepFilterRequest: {
            value: components["schemas"]["JSONValue"];
            /**
             * Disabled
             * @default false
             */
            disabled: boolean;
        };
        /**
         * StepFilterResponse
         * @description Filter attached to a step.
         */
        StepFilterResponse: {
            /** Name */
            name: string;
            value: components["schemas"]["JSONValue"];
            /**
             * Disabled
             * @default false
             */
            disabled: boolean;
        };
        /** StepFilterSpec */
        StepFilterSpec: {
            /** Name */
            name: string;
            value: components["schemas"]["JSONValue"];
            /**
             * Disabled
             * @default false
             */
            disabled: boolean;
        };
        /**
         * StepFiltersResponse
         * @description Container for step filters.
         */
        StepFiltersResponse: {
            /** Filters */
            filters: components["schemas"]["StepFilterResponse"][];
        };
        /**
         * StepReportRequest
         * @description Request to run a step report.
         */
        StepReportRequest: {
            /**
             * Reportname
             * @default standard
             */
            reportName: string;
            config?: components["schemas"]["JSONObject"];
        };
        /**
         * StepReportResponse
         * @description Report configuration attached to a step.
         */
        StepReportResponse: {
            /**
             * Reportname
             * @default standard
             */
            reportName: string;
            config?: components["schemas"]["JSONObject"];
        };
        /**
         * StepReportRunResponse
         * @description Result of running a step report.
         */
        StepReportRunResponse: {
            report: components["schemas"]["StepReportResponse"];
            wdk?: components["schemas"]["JSONObject"] | null;
        };
        /** StepReportSpec */
        "StepReportSpec-Input": {
            /**
             * Reportname
             * @default standard
             */
            reportName: string;
            config?: components["schemas"]["JSONObject"];
        };
        /** StepReportSpec */
        "StepReportSpec-Output": {
            /**
             * Reportname
             * @default standard
             */
            reportName: string;
            config?: components["schemas"]["JSONObject"];
        };
        /**
         * StepResponse
         * @description Strategy step.
         */
        StepResponse: {
            /** Id */
            id: string;
            /** Kind */
            kind?: string | null;
            /** Displayname */
            displayName: string;
            /** Searchname */
            searchName?: string | null;
            /** Recordtype */
            recordType?: string | null;
            parameters?: components["schemas"]["JSONObject"] | null;
            /** Operator */
            operator?: string | null;
            colocationParams?: components["schemas"]["JSONObject"] | null;
            /** Primaryinputstepid */
            primaryInputStepId?: string | null;
            /** Secondaryinputstepid */
            secondaryInputStepId?: string | null;
            /** Resultcount */
            resultCount?: number | null;
            /** Wdkstepid */
            wdkStepId?: number | null;
            /** Filters */
            filters?: components["schemas"]["StepFilterResponse"][] | null;
            /** Analyses */
            analyses?: components["schemas"]["StepAnalysisResponse"][] | null;
            /** Reports */
            reports?: components["schemas"]["StepReportResponse"][] | null;
        };
        /** StrategyPlan */
        "StrategyPlan-Input": {
            /** Recordtype */
            recordType: string;
            root: components["schemas"]["PlanNode-Input"];
            metadata?: components["schemas"]["PlanMetadata"] | null;
        } & {
            [key: string]: unknown;
        };
        /** StrategyPlan */
        "StrategyPlan-Output": {
            /** Recordtype */
            recordType: string;
            root: components["schemas"]["PlanNode-Output"];
            metadata?: components["schemas"]["PlanMetadata"] | null;
        } & {
            [key: string]: unknown;
        };
        /**
         * StrategyResponse
         * @description Full strategy with steps.
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
            steps: components["schemas"]["StepResponse"][];
            /** Rootstepid */
            rootStepId: string | null;
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
        };
        /**
         * StrategySummaryResponse
         * @description Strategy summary for list views.
         */
        StrategySummaryResponse: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Title */
            title?: string | null;
            /** Siteid */
            siteId: string;
            /** Recordtype */
            recordType: string | null;
            /** Stepcount */
            stepCount: number;
            /** Resultcount */
            resultCount?: number | null;
            /** Wdkstrategyid */
            wdkStrategyId?: number | null;
            /**
             * Issaved
             * @default false
             */
            isSaved: boolean;
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
         * ThresholdSweepRequest
         * @description Request to sweep a numeric parameter across a range.
         */
        ThresholdSweepRequest: {
            /** Parametername */
            parameterName: string;
            /** Minvalue */
            minValue: number;
            /** Maxvalue */
            maxValue: number;
            /**
             * Steps
             * @default 10
             */
            steps: number;
        };
        /** TokenPayload */
        TokenPayload: {
            /** Token */
            token: string;
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
        /** UpdatePlanSessionRequest */
        UpdatePlanSessionRequest: {
            /** Title */
            title?: string | null;
        };
        /**
         * UpdateStrategyRequest
         * @description Request to update a strategy.
         */
        UpdateStrategyRequest: {
            /** Name */
            name?: string | null;
            plan?: components["schemas"]["StrategyPlan-Input"] | null;
            /** Wdkstrategyid */
            wdkStrategyId?: number | null;
            /** Issaved */
            isSaved?: boolean | null;
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
         * WdkStrategySummaryResponse
         * @description WDK strategy summary for list views.
         */
        WdkStrategySummaryResponse: {
            /** Wdkstrategyid */
            wdkStrategyId: number;
            /** Name */
            name: string;
            /** Siteid */
            siteId: string;
            /** Wdkurl */
            wdkUrl?: string | null;
            /** Rootstepid */
            rootStepId?: number | null;
            /** Issaved */
            isSaved?: boolean | null;
            /**
             * Isinternal
             * @default false
             */
            isInternal: boolean;
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
    get_site_api_v1_sites__siteId__get: {
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
                    "application/json": components["schemas"]["SiteResponse"];
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
    get_search_details_api_v1_sites__siteId__searches__recordType___searchName__get: {
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
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SearchDetailsResponse"];
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
    get_dependent_params_api_v1_sites__siteId__searches__recordType___searchName__dependent_params_post: {
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
                "application/json": components["schemas"]["DependentParamsRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DependentParamsResponse"];
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
    get_param_specs_api_v1_sites__siteId__searches__recordType___searchName__param_specs_get: {
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
        requestBody?: never;
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
                    "application/json": {
                        [key: string]: unknown;
                    };
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
    list_plans_api_v1_plans_get: {
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
                    "application/json": components["schemas"]["PlanSessionSummaryResponse"][];
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
    open_plan_api_v1_plans_open_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["OpenPlanSessionRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["OpenPlanSessionResponse"];
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
    get_plan_api_v1_plans__planSessionId__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                planSessionId: string;
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
                    "application/json": components["schemas"]["PlanSessionResponse"];
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
    delete_plan_api_v1_plans__planSessionId__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                planSessionId: string;
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
    update_plan_api_v1_plans__planSessionId__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                planSessionId: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UpdatePlanSessionRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PlanSessionSummaryResponse"];
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
                    "application/json": components["schemas"]["StrategySummaryResponse"][];
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
    list_wdk_strategies_api_v1_strategies_wdk_get: {
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
                    "application/json": components["schemas"]["WdkStrategySummaryResponse"][];
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
                    "application/json": components["schemas"]["StrategySummaryResponse"][];
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
    delete_wdk_strategy_api_v1_strategies_wdk__wdkStrategyId__delete: {
        parameters: {
            query: {
                siteId: string;
            };
            header?: never;
            path: {
                wdkStrategyId: number;
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
    import_wdk_strategy_api_v1_strategies_wdk__wdkStrategyId__import_post: {
        parameters: {
            query: {
                siteId: string;
            };
            header?: never;
            path: {
                wdkStrategyId: number;
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
    sync_strategy_from_wdk_api_v1_strategies__strategyId__sync_wdk_post: {
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
    get_step_api_v1_strategies__strategyId__steps__step_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                strategyId: string;
                step_id: string;
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
                    "application/json": components["schemas"]["StepResponse"];
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
    list_step_filters_api_v1_strategies__strategyId__steps__step_id__filters_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                strategyId: string;
                step_id: string;
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
                    "application/json": components["schemas"]["StepFilterResponse"][];
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
    list_available_filters_api_v1_strategies__strategyId__steps__step_id__filters_available_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                strategyId: string;
                step_id: string;
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
                    "application/json": components["schemas"]["JSONArray"];
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
    set_step_filter_api_v1_strategies__strategyId__steps__step_id__filters__filter_name__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                strategyId: string;
                step_id: string;
                filter_name: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StepFilterRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StepFiltersResponse"];
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
    delete_step_filter_api_v1_strategies__strategyId__steps__step_id__filters__filter_name__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                strategyId: string;
                step_id: string;
                filter_name: string;
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
                    "application/json": components["schemas"]["StepFiltersResponse"];
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
    list_analysis_types_api_v1_strategies__strategyId__steps__step_id__analysis_types_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                strategyId: string;
                step_id: string;
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
                    "application/json": components["schemas"]["JSONArray"];
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
    get_analysis_type_api_v1_strategies__strategyId__steps__step_id__analysis_types__analysis_type__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                strategyId: string;
                step_id: string;
                analysis_type: string;
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
    list_step_analyses_api_v1_strategies__strategyId__steps__step_id__analyses_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                strategyId: string;
                step_id: string;
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
                    "application/json": components["schemas"]["JSONArray"];
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
    run_step_analysis_api_v1_strategies__strategyId__steps__step_id__analyses_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                strategyId: string;
                step_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StepAnalysisRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StepAnalysisRunResponse"];
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
    run_step_report_api_v1_strategies__strategyId__steps__step_id__reports_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                strategyId: string;
                step_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StepReportRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StepReportRunResponse"];
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
    preview_results_api_v1_results_preview_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PreviewRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PreviewResponse"];
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
    download_results_api_v1_results_download_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DownloadRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DownloadResponse"];
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
    list_experiments_api_v1_experiments_get: {
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
    create_experiment_api_v1_experiments_post: {
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
            /** @description SSE stream of experiment progress */
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
    list_importable_strategies_api_v1_experiments_importable_strategies_get: {
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
    get_strategy_details_api_v1_experiments_importable_strategies__strategy_id__details_get: {
        parameters: {
            query: {
                siteId: string;
            };
            header?: never;
            path: {
                strategy_id: number;
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
                "application/json": {
                    [key: string]: unknown;
                };
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
            /** @description SSE stream of batch experiment progress */
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
                dir?: string;
                attributes?: string | null;
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
                "application/json": {
                    [key: string]: unknown;
                };
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
    get_experiment_strategy_api_v1_experiments__experiment_id__strategy_get: {
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
    get_experiment_distribution_api_v1_experiments__experiment_id__results_distributions__attribute_name__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                experiment_id: string;
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
    get_experiment_analysis_types_api_v1_experiments__experiment_id__analyses_types_get: {
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
    run_experiment_analysis_api_v1_experiments__experiment_id__analyses_run_post: {
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
                "application/json": {
                    [key: string]: unknown;
                };
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
                "application/json": {
                    [key: string]: unknown;
                };
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
    step_contributions_api_v1_experiments__experiment_id__step_contributions_post: {
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
                "application/json": {
                    [key: string]: unknown;
                };
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
    ai_assist_api_v1_experiments_ai_assist_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AiAssistRequest"];
            };
        };
        responses: {
            /** @description SSE stream of AI assistant response */
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
    login_with_password_api_v1_veupathdb_auth_login_post: {
        parameters: {
            query: {
                siteId: string;
                redirectTo?: string | null;
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
    accept_token_api_v1_veupathdb_auth_token_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["TokenPayload"] | null;
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
                    "application/json": components["schemas"]["AuthSuccessResponse"];
                };
            };
        };
    };
    refresh_internal_auth_api_v1_veupathdb_auth_refresh_post: {
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
                    "application/json": components["schemas"]["AuthSuccessResponse"];
                };
            };
        };
    };
    auth_status_api_v1_veupathdb_auth_status_get: {
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
}
