from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

from aa_content.baseline_research import run_baseline_research
from aa_content.config import load_openai_config
from aa_content.content_angle import (
    approve_custom_angle,
    approve_generated_angle,
    propose_content_angles,
    run_angle_research,
)
from aa_content.errors import StageExecutionError, UserFacingError
from aa_content.models import VersionComponent
from aa_content.narration import generate_narration
from aa_content.processing_workflow import process_itinerary
from aa_content.production_brief import generate_production_brief
from aa_content.validation import (
    QUALITY_BENCHMARK,
    acknowledge_finding,
    validate_package,
)
from aa_content.versioning import approve_component, get_version_status, submit_review
from aa_content.youtube_packaging import generate_youtube_packaging
from aa_content.route_segments import (
    confirm_route_segment,
    list_route_segments,
    propose_shared_route_segments,
)
from aa_content.trip_workflow import (
    create_trip,
    inspect_trip,
    resolve_url_source,
    update_trip,
)
from aa_content.workspace import initialize_workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aa-content")
    parser.add_argument(
        "--workspace",
        required=True,
        type=Path,
        help="Workspace containing aa_content.db and Trip artifacts.",
    )

    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="Initialize a shared Adventure Asia workspace.")

    trip_parser = commands.add_parser("trip", help="Manage Trips.")
    trip_commands = trip_parser.add_subparsers(dest="trip_command", required=True)
    create_parser = trip_commands.add_parser(
        "create", help="Create a Trip from itinerary text pasted through stdin."
    )
    create_parser.add_argument("--name", required=True, help="Readable Trip name.")
    create_parser.add_argument(
        "--url", help="Ingest itinerary content from a webpage URL instead of stdin."
    )
    create_parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate readable Trip artifacts from persisted state.",
    )
    show_parser = trip_commands.add_parser(
        "show", help="Inspect persisted Trip and workflow state."
    )
    show_parser.add_argument("--trip-id", required=True, help="Stable Trip ID.")
    update_parser = trip_commands.add_parser(
        "update",
        help="Create the next immutable Itinerary Revision for an existing Trip.",
    )
    update_parser.add_argument("--trip-id", required=True, help="Stable Trip ID.")
    update_parser.add_argument(
        "--url", help="Re-ingest itinerary content from a webpage URL instead of stdin."
    )
    update_parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess even if content is unchanged, or recover a stuck update.",
    )
    process_parser = trip_commands.add_parser(
        "process", help="Sanitize and normalize the current Itinerary Revision."
    )
    process_parser.add_argument("--trip-id", required=True, help="Stable Trip ID.")
    process_parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate sanitized and normalized revision artifacts.",
    )
    research_parser = trip_commands.add_parser(
        "research", help="Run Baseline Research for the current Itinerary Revision."
    )
    research_parser.add_argument("--trip-id", required=True, help="Stable Trip ID.")
    research_parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate every Baseline Research category.",
    )

    angle_parser = trip_commands.add_parser(
        "angle", help="Propose, approve, and research a Content Angle."
    )
    angle_commands = angle_parser.add_subparsers(
        dest="angle_command", required=True
    )
    angle_propose_parser = angle_commands.add_parser(
        "propose", help="Propose up to three evidence-backed Content Angles."
    )
    angle_propose_parser.add_argument(
        "--trip-id", required=True, help="Stable Trip ID."
    )
    angle_approve_parser = angle_commands.add_parser(
        "approve", help="Approve a proposed or custom Content Angle."
    )
    angle_approve_parser.add_argument(
        "--trip-id", required=True, help="Stable Trip ID."
    )
    angle_approve_parser.add_argument(
        "--angle-id", help="Approve this previously proposed Content Angle."
    )
    angle_approve_parser.add_argument(
        "--custom", help="Approve a custom viewer-question Content Angle instead."
    )
    angle_approve_parser.add_argument(
        "--acknowledge-unsupported",
        action="store_true",
        help="Approve a custom angle even without matching Baseline Evidence.",
    )
    angle_research_parser = angle_commands.add_parser(
        "research", help="Run Angle Research for the currently approved angle."
    )
    angle_research_parser.add_argument(
        "--trip-id", required=True, help="Stable Trip ID."
    )
    angle_research_parser.add_argument(
        "--force", action="store_true", help="Regenerate Angle Research."
    )

    narrate_parser = trip_commands.add_parser(
        "narrate", help="Generate evidence-traceable narration for the approved angle."
    )
    narrate_parser.add_argument("--trip-id", required=True, help="Stable Trip ID.")
    narrate_parser.add_argument(
        "--editorial-notes",
        default="",
        help="Optional Editorial Notes supporting Editorial Judgment.",
    )
    narrate_parser.add_argument(
        "--force", action="store_true", help="Regenerate the narration."
    )

    validate_parser = trip_commands.add_parser(
        "validate", help="Review the draft Editorial Package."
    )
    validate_parser.add_argument("--trip-id", required=True, help="Stable Trip ID.")
    validate_acknowledge_parser = trip_commands.add_parser(
        "validate-acknowledge",
        help="Approver acknowledgment of an advisory validation finding.",
    )
    validate_acknowledge_parser.add_argument(
        "--trip-id", required=True, help="Stable Trip ID."
    )
    validate_acknowledge_parser.add_argument(
        "--finding-id", required=True, help="Finding id to acknowledge."
    )
    validate_acknowledge_parser.add_argument(
        "--approver", required=True, help="Approver identity."
    )

    submit_parser = trip_commands.add_parser(
        "submit-review",
        help="Create the next immutable Editorial Package Version.",
    )
    submit_parser.add_argument("--trip-id", required=True, help="Stable Trip ID.")

    approve_component_parser = trip_commands.add_parser(
        "approve",
        help="Approver approval of a controlled component or the complete version.",
    )
    approve_component_parser.add_argument(
        "--trip-id", required=True, help="Stable Trip ID."
    )
    approve_component_parser.add_argument(
        "--component",
        required=True,
        choices=["NARRATION", "FINAL"],
        help="Which controlled component to approve.",
    )
    approve_component_parser.add_argument(
        "--approver", required=True, help="Approver identity."
    )

    version_status_parser = trip_commands.add_parser(
        "version-status",
        help="Show the latest Editorial Package Version and approval status.",
    )
    version_status_parser.add_argument(
        "--trip-id", required=True, help="Stable Trip ID."
    )

    youtube_parser = trip_commands.add_parser(
        "youtube-packaging",
        help="Generate YouTube titles, description, chapters, thumbnail brief, "
        "keywords, and Shorts from the latest submitted version.",
    )
    youtube_parser.add_argument("--trip-id", required=True, help="Stable Trip ID.")

    production_brief_parser = trip_commands.add_parser(
        "production-brief",
        help="Generate the vendor-neutral Production Brief and manual "
        "Pictory handoff files.",
    )
    production_brief_parser.add_argument(
        "--trip-id", required=True, help="Stable Trip ID."
    )

    segment_parser = commands.add_parser(
        "route-segment", help="Manage shared Research Library Route Segments."
    )
    segment_commands = segment_parser.add_subparsers(
        dest="segment_command", required=True
    )
    propose_parser = segment_commands.add_parser(
        "propose",
        help="Propose Route Segments shared between two Trips' route legs.",
    )
    propose_parser.add_argument("--trip-a", required=True, help="First Trip ID.")
    propose_parser.add_argument("--trip-b", required=True, help="Second Trip ID.")
    confirm_parser = segment_commands.add_parser(
        "confirm", help="Operator confirmation making a Route Segment canonical."
    )
    confirm_parser.add_argument(
        "--segment-id", required=True, help="Route Segment ID to confirm."
    )
    list_parser = segment_commands.add_parser(
        "list", help="List Route Segments associated with a Trip."
    )
    list_parser.add_argument("--trip-id", required=True, help="Stable Trip ID.")

    config_parser = commands.add_parser("config", help="Validate local configuration.")
    config_commands = config_parser.add_subparsers(
        dest="config_command", required=True
    )
    config_commands.add_parser(
        "check-openai",
        help="Verify that OPENAI_API_KEY is available from the workspace .env.",
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    options = build_parser().parse_args(arguments)

    try:
        if options.command == "init":
            reused = initialize_workspace(options.workspace)
            state = "already initialized" if reused else "initialized"
            print(f"Workspace {state}: {options.workspace.resolve()}")
            return 0

        if options.command == "trip" and options.trip_command == "create":
            if options.url:
                source, fetch = resolve_url_source(options.workspace, options.url)
                result = create_trip(
                    options.workspace,
                    options.name,
                    source.text,
                    force=options.force,
                    source_kind=source.kind,
                    source_url=source.requested_url,
                    source_fetch=fetch,
                )
            else:
                result = create_trip(
                    options.workspace,
                    options.name,
                    sys.stdin.read(),
                    force=options.force,
                )
            print(f"Trip {result.outcome}: {result.name}")
            print(f"Trip ID: {result.trip_id}")
            print(f"Itinerary Revision: r{result.revision_number}")
            return 0

        if options.command == "trip" and options.trip_command == "show":
            result = inspect_trip(options.workspace, options.trip_id)
            source_path = result.source_path.relative_to(
                options.workspace
            ).as_posix()
            print(f"Trip: {result.name}")
            print(f"Trip ID: {result.trip_id}")
            print(f"Slug: {result.slug}")
            print(f"Current Itinerary Revision: r{result.revision_number}")
            print(f"Trip Creation: {result.creation_status}")
            print(f"Source: {source_path}")
            if result.working_review_status is not None:
                print(f"Working Review: {result.working_review_status}")
            return 0

        if options.command == "trip" and options.trip_command == "update":
            if options.url:
                source, fetch = resolve_url_source(
                    options.workspace, options.url, trip_id=options.trip_id
                )
                result = update_trip(
                    options.workspace,
                    options.trip_id,
                    source.text,
                    force=options.force,
                    source_kind=source.kind,
                    source_url=source.requested_url,
                    source_fetch=fetch,
                )
            else:
                result = update_trip(
                    options.workspace,
                    options.trip_id,
                    sys.stdin.read(),
                    force=options.force,
                )
            print(f"Itinerary {result.outcome}: {result.name}")
            print(f"Trip ID: {result.trip_id}")
            print(f"Itinerary Revision: r{result.revision_number}")
            if result.previous_revision_number is not None:
                print(f"Previous Itinerary Revision: r{result.previous_revision_number}")
            return 0

        if options.command == "trip" and options.trip_command == "process":
            result = process_itinerary(
                options.workspace, options.trip_id, force=options.force
            )
            removal_label = "removal" if result.finding_count == 1 else "removals"
            print(f"Itinerary {result.outcome}: {result.name}")
            print(f"Trip ID: {result.trip_id}")
            print(f"Itinerary Revision: r{result.revision_number}")
            print(
                f"Supplier Data: {result.sanitization_status} "
                f"({result.finding_count} {removal_label})"
            )
            print(f"Missing Information: {result.missing_information_count}")
            print(f"Fact Conflicts: {result.fact_conflict_count}")
            print(f"Export: {'BLOCKED' if result.export_blocked else 'READY'}")
            return 0

        if options.command == "trip" and options.trip_command == "research":
            result = run_baseline_research(
                options.workspace, options.trip_id, force=options.force
            )
            print(f"Baseline Research {result.outcome}: {result.name}")
            print(f"Trip ID: {result.trip_id}")
            print(f"Itinerary Revision: r{result.revision_number}")
            for claim in result.claims:
                recheck = (
                    f", recheck {claim.recheck_date}" if claim.recheck_date else ""
                )
                stale = " [STALE — refresh failed]" if claim.stale else ""
                print(
                    f"  {claim.category}: {claim.evidence_status} "
                    f"({len(claim.sources)} sources{recheck}){stale}"
                )
            print(f"Missing Information: {len(result.missing_categories)}")
            return 0

        if options.command == "trip" and options.trip_command == "angle":
            if options.angle_command == "propose":
                result = propose_content_angles(options.workspace, options.trip_id)
                print(f"Proposed Content Angles: {len(result.options)}")
                for option in result.options:
                    print(f"  {option.angle_id}: {option.viewer_question}")
                    print(f"    Evidence: {', '.join(option.available_evidence)}")
                    print(f"    Commercial relevance: {option.commercial_relevance}")
                    print(f"    Risks: {option.risks}")
                    if option.missing_information:
                        print(
                            "    Missing Information: "
                            + ", ".join(option.missing_information)
                        )
                return 0

            if options.angle_command == "approve":
                if options.custom:
                    approval = approve_custom_angle(
                        options.workspace,
                        options.trip_id,
                        options.custom,
                        acknowledge_unsupported=options.acknowledge_unsupported,
                    )
                elif options.angle_id:
                    approval = approve_generated_angle(
                        options.workspace, options.trip_id, options.angle_id
                    )
                else:
                    print(
                        "Error: pass --angle-id or --custom.", file=sys.stderr
                    )
                    return 2
                print(f"Content Angle approved: {approval.angle.angle_id}")
                print(f"Viewer question: {approval.angle.viewer_question}")
                print(f"Evidence support: {approval.angle.evidence_support}")
                return 0

            if options.angle_command == "research":
                result = run_angle_research(
                    options.workspace, options.trip_id, force=options.force
                )
                print(f"Angle Research {result.outcome}: {result.name}")
                print(f"Trip ID: {result.trip_id}")
                print(f"Angle: {result.angle.viewer_question}")
                if result.claim is not None:
                    print(
                        f"Evidence: {result.claim.evidence_status} "
                        f"({len(result.claim.sources)} sources)"
                    )
                    if result.claim.evidence_status in (
                        "UNKNOWN",
                        "INDICATIVE",
                    ):
                        print(
                            "Warning: Angle Research evidence is weak; "
                            "review before narration."
                        )
                return 0

        if options.command == "trip" and options.trip_command == "narrate":
            result = generate_narration(
                options.workspace,
                options.trip_id,
                editorial_notes=options.editorial_notes,
                force=options.force,
            )
            print(f"Narration {result.outcome}: {result.name}")
            print(f"Trip ID: {result.trip_id}")
            print(f"Angle: {result.angle.viewer_question}")
            print(f"Word count: {result.word_count}")
            print(f"Estimated duration: {result.estimated_minutes} min")
            if result.overall_intensity is not None:
                print(f"Overall Intensity: {result.overall_intensity}/5")
            for warning in result.warnings:
                print(f"Warning: {warning}")
            return 0

        if options.command == "trip" and options.trip_command == "validate-acknowledge":
            acknowledgment = acknowledge_finding(
                options.workspace,
                options.trip_id,
                options.finding_id,
                options.approver,
            )
            print(f"Acknowledged: {acknowledgment.finding_id}")
            print(f"Approver: {acknowledgment.approver}")
            print(f"Timestamp: {acknowledgment.acknowledged_at}")
            print(f"Draft version: {acknowledgment.draft_signature[:12]}")
            return 0

        if options.command == "trip" and options.trip_command == "validate":
            report = validate_package(options.workspace, options.trip_id)
            print(f"Validation for: {report.name}")
            print(f"Trip ID: {report.trip_id}")
            print(f"Draft version: {report.draft_signature[:12]}")
            print(f"Quality Score: {report.quality_score}/100")
            if report.quality_score < QUALITY_BENCHMARK:
                print(
                    f"Below benchmark ({QUALITY_BENCHMARK}); remains "
                    "reviewable and exportable after Approver acknowledgment."
                )
            print(f"Export: {'BLOCKED' if report.export_blocked else 'READY'}")
            if not report.findings:
                print("No findings.")
            for finding in report.findings:
                acknowledged = (
                    " [ACKNOWLEDGED]"
                    if finding.finding_id in report.acknowledged_ids
                    else ""
                )
                print(
                    f"  [{finding.severity}] {finding.code}: {finding.message}"
                    f"{acknowledged}"
                )
            return 0

        if options.command == "trip" and options.trip_command == "submit-review":
            version = submit_review(options.workspace, options.trip_id)
            print(f"Submitted: {version.version_label}")
            print(f"Trip ID: {version.trip_id}")
            print(f"Content Angle: {version.angle_id}")
            print(f"Quality Score: {version.quality_score}/100")
            print(f"Export: {'BLOCKED' if version.export_blocked else 'READY'}")
            print(f"Content integrity: {version.content_hash[:12]}")
            return 0

        if options.command == "trip" and options.trip_command == "approve":
            approval = approve_component(
                options.workspace,
                options.trip_id,
                VersionComponent(options.component),
                options.approver,
            )
            print(f"Approved: {approval.component} for v{approval.version_number}")
            print(f"Approver: {approval.approver}")
            print(f"Timestamp: {approval.approved_at}")
            print(f"Content integrity: {approval.content_integrity_reference[:12]}")
            return 0

        if options.command == "trip" and options.trip_command == "version-status":
            status = get_version_status(options.workspace, options.trip_id)
            print(f"Trip: {status.trip.name}")
            print(f"Latest version: {status.version.version_label}")
            print(f"Quality Score: {status.version.quality_score}/100")
            print(
                f"Export: {'BLOCKED' if status.version.export_blocked else 'READY'}"
            )
            for component in status.components:
                approver = (
                    f" (approved by {component.approval.approver})"
                    if component.approval is not None
                    else ""
                )
                print(f"  {component.component}: {component.validity}{approver}")
            return 0

        if options.command == "trip" and options.trip_command == "youtube-packaging":
            result = generate_youtube_packaging(options.workspace, options.trip_id)
            packaging = result.packaging
            print(f"YouTube packaging {result.outcome}: {result.name}")
            print(f"Trip ID: {result.trip_id}")
            print("Titles:")
            for title in packaging.titles:
                print(f"  [{title.style}] {title.text}")
            print(f"Chapters: {len(packaging.chapters)}")
            print(f"Keywords: {len(packaging.keywords)}")
            print(f"Shorts: {len(packaging.shorts)}")
            print(f"Content signature: {result.content_signature[:12]}")
            return 0

        if options.command == "trip" and options.trip_command == "production-brief":
            result = generate_production_brief(options.workspace, options.trip_id)
            brief = result.brief
            print(f"Production Brief {result.outcome}: {result.name}")
            print(f"Trip ID: {result.trip_id}")
            print(f"Scene requirements: {len(brief.scene_requirements)}")
            print(f"Acknowledged warnings included: {len(brief.warnings)}")
            print(f"Content signature: {result.content_signature[:12]}")
            return 0

        if options.command == "route-segment" and options.segment_command == "propose":
            segments = propose_shared_route_segments(
                options.workspace, options.trip_a, options.trip_b
            )
            print(f"Proposed Route Segments: {len(segments)}")
            for segment in segments:
                print(
                    f"  {segment.route_segment_id}: {segment.origin} -> "
                    f"{segment.destination} ({segment.status})"
                )
            return 0

        if options.command == "route-segment" and options.segment_command == "confirm":
            segment = confirm_route_segment(options.workspace, options.segment_id)
            print(
                f"Route Segment confirmed: {segment.route_segment_id} "
                f"({segment.origin} -> {segment.destination})"
            )
            return 0

        if options.command == "route-segment" and options.segment_command == "list":
            segments = list_route_segments(options.workspace, options.trip_id)
            print(f"Route Segments: {len(segments)}")
            for segment in segments:
                print(
                    f"  {segment.route_segment_id}: {segment.origin} -> "
                    f"{segment.destination} ({segment.status})"
                )
            return 0

        if options.command == "config" and options.config_command == "check-openai":
            load_openai_config(options.workspace)
            print("OpenAI configuration ready.")
            return 0
    except StageExecutionError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except UserFacingError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    return 2
