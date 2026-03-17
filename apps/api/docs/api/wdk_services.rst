WDK Services
=============

WDK integration services that bridge PathFinder's domain model with VEuPathDB's
WDK REST API. These services handle enrichment orchestration, record type
resolution, step result browsing, and shared WDK helpers.

Overview
--------

The WDK services layer sits between the transport/tool layers and the raw
``integrations.veupathdb`` HTTP client. Where the integration layer handles
HTTP communication, these services add business logic: enrichment orchestration,
fuzzy record-type matching, result pagination, and attribute inspection.

Design Decisions
~~~~~~~~~~~~~~~~

**Why a separate WDK service layer?** The integration layer
(``integrations.veupathdb``) is a thin HTTP client. WDK services add domain
logic that multiple consumers need: experiments, gene sets, workbench, and
export all need step result browsing with consistent attribute handling. Sharing
this logic avoids duplication.

**Fuzzy record-type matching:** WDK record type names vary between sites
(``GeneRecordClasses.GeneRecordClass`` vs ``gene``). The resolver uses
three-stage matching (exact → name → display) with disambiguation to handle
this reliably.

Enrichment Service
------------------

**Purpose:** Unified enrichment orchestration. Runs GO/pathway enrichment
via WDK, handles multiple enrichment types, and formats results for the
experiment analysis pipeline.

.. automodule:: veupath_chatbot.services.wdk.enrichment_service
   :members:
   :undoc-members:
   :show-inheritance:

WDK Helpers
-----------

**Purpose:** Shared WDK helpers for record parsing, attribute inspection,
and parameter merging. Used across experiments, gene sets, and workbench.

.. automodule:: veupath_chatbot.services.wdk.helpers
   :members:
   :undoc-members:
   :show-inheritance:

Record Type Resolution
----------------------

**Purpose:** Resolve record type names with fuzzy matching. Three-stage
matching (exact, name, display) handles WDK's inconsistent naming across
sites.

.. automodule:: veupath_chatbot.services.wdk.record_types
   :members:
   :undoc-members:
   :show-inheritance:

Step Results Service
--------------------

**Purpose:** Shared service for browsing WDK step results. Encapsulates
attribute listing, record retrieval, distribution computation, and analysis
endpoint logic. Used by experiments, gene sets, and workbench endpoints.

.. automodule:: veupath_chatbot.services.wdk.step_results
   :members:
   :undoc-members:
   :show-inheritance:
