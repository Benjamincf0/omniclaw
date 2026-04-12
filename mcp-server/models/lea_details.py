from __future__ import annotations

import re
import sys
from html import unescape
from pathlib import Path
from urllib.parse import unquote, urljoin

from bs4 import BeautifulSoup, NavigableString, Tag
from pydantic import BaseModel, Field

# Ensure the mcp-server root is importable regardless of how this module is loaded
_SERVER_ROOT = Path(__file__).resolve().parent.parent
if str(_SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(_SERVER_ROOT))

from models.lea_classes import LeaMetric, _build_headers  # noqa: E402
from models.news import OMNIVOX_BASE, _normalize_text  # noqa: E402
from omnivox_client import omnivox_request_url  # noqa: E402

_COURSE_HEADER_PATTERN = re.compile(
    r"^([A-Z0-9]{3}-[A-Z0-9]{3}-[A-Z0-9]{2})\s+(.*?)\s+(?:section|sect\.)\s+([A-Z0-9]+)$",
    re.IGNORECASE,
)
_COURSE_SECTION_ONLY_PATTERN = re.compile(
    r"^([A-Z0-9]{3}-[A-Z0-9]{3}-[A-Z0-9]{2})\s+(?:section|sect\.)\s+([A-Z0-9]+)$",
    re.IGNORECASE,
)
_OPEN_CENTRE_PATTERN = re.compile(r"OpenCentre\(\s*'([^']+)'")
_CALL_PAGE_PATTERN = re.compile(r"CallPageVisualiseDocument\('([^']+)'")
_EXTERNAL_LINK_PATTERN = re.compile(r"ValiderLienDocExterne\('([^']+)'\)")
_URL_IN_STRING_PATTERN = re.compile(r"'(https?://[^']+)'")
_FILE_SIZE_PATTERN = re.compile(r"^(?P<name>.+?)\s+(?P<size>\d+(?:\.\d+)?\s*(?:KB|MB|GB))$")
_PUBLISHED_PATTERN = re.compile(r"^Published by\s+(.*?)\s+on\s+(.*)$", re.IGNORECASE)


class LeaLinkReq(BaseModel):
    link: str


class LeaCourseContext(BaseModel):
    header: str = ""
    course_code: str = ""
    course_title: str = ""
    section: str = ""


class LeaDocumentItem(BaseModel):
    title: str
    description: str = ""
    distributed_at: str = ""
    view_url: str | None = None
    external_url: str | None = None
    file_name: str = ""
    file_size: str = ""
    is_new: bool = False


class LeaDocumentCategory(BaseModel):
    title: str
    items: list[LeaDocumentItem] = Field(default_factory=list)


class LeaDocumentsRes(BaseModel):
    page_title: str
    course: LeaCourseContext
    instructions: str = ""
    printable_url: str | None = None
    categories: list[LeaDocumentCategory] = Field(default_factory=list)


class LeaAssignmentSubmission(BaseModel):
    label: str = ""
    submitted_at: str = ""
    file_name: str = ""
    download_url: str | None = None


class LeaAssignmentItem(BaseModel):
    title: str
    instruction_url: str | None = None
    deadline: str = ""
    submission_method: str = ""
    status: str = ""
    corrected_copy_url: str | None = None
    corrected_copy_name: str = ""
    description: str = ""
    linked_document_url: str | None = None
    linked_document_name: str = ""
    submit_instructions: str = ""
    resubmit_instructions: str = ""
    comment_instructions: str = ""
    upload_max_size: str = ""
    submissions: list[LeaAssignmentSubmission] = Field(default_factory=list)
    is_new: bool = False


class LeaAssignmentsRes(BaseModel):
    page_title: str
    course: LeaCourseContext
    instructions: str = ""
    printable_url: str | None = None
    assignments: list[LeaAssignmentItem] = Field(default_factory=list)


class LeaAssignmentContentRes(BaseModel):
    page_title: str
    course: LeaCourseContext
    title: str
    description: str = ""
    instructions: str = ""
    linked_document_url: str | None = None
    linked_document_name: str = ""
    status: str = ""
    corrected_copy_url: str | None = None
    corrected_copy_name: str = ""
    deadline: str = ""
    submit_instructions: str = ""
    resubmit_instructions: str = ""
    comment_instructions: str = ""
    upload_max_size: str = ""
    submissions: list[LeaAssignmentSubmission] = Field(default_factory=list)
    printable_url: str | None = None


class LeaGradeAssessment(BaseModel):
    index: str = ""
    title: str
    note: str = ""
    mark: str = ""
    percentage: str = ""
    class_average: str = ""
    weight: str = ""
    weighted_points: str = ""
    discarded: bool = False


class LeaGradeCategory(BaseModel):
    title: str
    weight: str = ""
    average: str = ""
    note: str = ""
    assessments: list[LeaGradeAssessment] = Field(default_factory=list)


class LeaGradesRes(BaseModel):
    page_title: str
    course: LeaCourseContext
    snapshot: str = ""
    teacher: str = ""
    printable_url: str | None = None
    summary_link: str | None = None
    summary: list[LeaMetric] = Field(default_factory=list)
    categories: list[LeaGradeCategory] = Field(default_factory=list)


class LeaAnnouncementRes(BaseModel):
    title: str
    course: LeaCourseContext
    published_by: str = ""
    published_on: str = ""
    content: str = ""
    printable_url: str | None = None


async def _fetch_response(link: str):
    absolute_url = urljoin(OMNIVOX_BASE, link)
    response = await omnivox_request_url(absolute_url, headers=_build_headers(absolute_url))
    response.raise_for_status()
    return response


def _text_with_breaks(node: Tag | None) -> str:
    if not isinstance(node, Tag):
        return ""
    working = BeautifulSoup(str(node), "html.parser")
    for ignored in working.select("script, style, noscript"):
        ignored.decompose()
    for br in working.find_all("br"):
        br.replace_with("\n")

    lines = [
        _normalize_text(raw.replace("\xa0", " "))
        for raw in working.get_text("\n").splitlines()
    ]
    return "\n".join(line for line in lines if line)


def _extract_lines(node: Tag | None) -> list[str]:
    text = _text_with_breaks(node)
    return [line for line in text.splitlines() if line]


def _extract_target_url(raw: str, base_url: str) -> str | None:
    value = raw.strip()
    if not value:
        return None
    if value.startswith(("http://", "https://", "/")):
        return urljoin(base_url, value)

    for pattern in (_OPEN_CENTRE_PATTERN, _CALL_PAGE_PATTERN, _URL_IN_STRING_PATTERN):
        match = pattern.search(value)
        if match:
            return urljoin(base_url, unescape(match.group(1)))
    if not value.lower().startswith(("javascript:", "mailto:", "#")):
        return urljoin(base_url, unescape(value))
    return None


def _extract_anchor_url(anchor: Tag | None, base_url: str) -> str | None:
    if not isinstance(anchor, Tag):
        return None

    href = anchor.get("href", "").strip()
    onclick = anchor.get("onclick", "").strip()
    for candidate in (href, onclick):
        resolved = _extract_target_url(candidate, base_url)
        if resolved is not None:
            return resolved
    return None


def _extract_external_url(anchor: Tag | None) -> str | None:
    if not isinstance(anchor, Tag):
        return None

    for raw in (anchor.get("href", ""), anchor.get("onclick", "")):
        match = _EXTERNAL_LINK_PATTERN.search(raw)
        if match:
            return unquote(match.group(1))
    return None


def _parse_course_context(raw_header: str) -> LeaCourseContext:
    header = _normalize_text(raw_header)
    if not header:
        return LeaCourseContext()

    match = _COURSE_HEADER_PATTERN.match(header)
    if not match:
        section_only = _COURSE_SECTION_ONLY_PATTERN.match(header)
        if section_only:
            return LeaCourseContext(
                header=header,
                course_code=section_only.group(1),
                section=section_only.group(2).strip(),
            )
        return LeaCourseContext(header=header)

    return LeaCourseContext(
        header=header,
        course_code=match.group(1),
        course_title=match.group(2).strip(),
        section=match.group(3).strip(),
    )


def _extract_printable_url(soup: BeautifulSoup, base_url: str) -> str | None:
    for node in soup.select("a, input[onclick], input[title='Printer friendly']"):
        if not isinstance(node, Tag):
            continue
        label = _normalize_text(node.get_text(" ", strip=True))
        title = _normalize_text(node.get("title", ""))
        onclick = node.get("onclick", "")
        if "print" not in (label + " " + title + " " + onclick).lower():
            continue
        url = _extract_anchor_url(node, base_url)
        if url:
            return url
    return None


def _selected_text(node: Tag | None) -> str:
    if not isinstance(node, Tag):
        return ""
    return _normalize_text(node.get_text(" ", strip=True))


def _empty_element(name: str) -> Tag:
    element = BeautifulSoup(f"<{name}></{name}>", "html.parser").find(name)
    assert isinstance(element, Tag)
    return element


def _extract_document_file_details(node: Tag) -> tuple[str, str]:
    raw = _normalize_text(node.get_text(" ", strip=True))
    if not raw:
        return "", ""
    match = _FILE_SIZE_PATTERN.match(raw)
    if not match:
        return raw, ""
    return match.group("name").strip(), match.group("size").strip()


def _extract_description(node: Tag) -> str:
    working = BeautifulSoup(str(node), "html.parser")
    for anchor in working.select("a.lblTitreDocumentDansListe"):
        anchor.decompose()
    description = _text_with_breaks(working)
    return description


def _extract_lea_documents(html: str, base_url: str) -> LeaDocumentsRes:
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("td.cvirContenuCVIR")
    if not isinstance(container, Tag):
        raise ValueError("Unable to locate the LEA documents content in the HTML response")

    page_title = _selected_text(container.select_one(".TitrePageLigne1"))
    course = _parse_course_context(_selected_text(container.select_one(".TitrePageLigne2")))
    instructions = _text_with_breaks(container.select_one("#tblExplicationsEtudiant"))

    categories: list[LeaDocumentCategory] = []
    for category_table in container.select("table.CategorieDocument.CategorieDocumentEtudiant"):
        if not isinstance(category_table, Tag):
            continue
        title_node = category_table.select_one(".DisDoc_TitreCategorie a")
        title = _normalize_text(title_node.get_text(" ", strip=True)) if isinstance(title_node, Tag) else ""
        if not title:
            continue

        items: list[LeaDocumentItem] = []
        for row in category_table.select("tbody > tr[id^='doc']"):
            if not isinstance(row, Tag):
                continue
            title_anchor = row.select_one("a.lblTitreDocumentDansListe")
            title_text = (
                _normalize_text(title_anchor.get_text(" ", strip=True))
                if isinstance(title_anchor, Tag)
                else ""
            )
            if not title_text:
                continue

            download_cell = row.select_one(".colVoirTelecharger")
            description_node = row.select_one(".divDescriptionDocumentDansListe")
            file_name, file_size = _extract_document_file_details(
                download_cell if isinstance(download_cell, Tag) else _empty_element("td")
            )
            items.append(
                LeaDocumentItem(
                    title=title_text,
                    description=_extract_description(
                        description_node
                        if isinstance(description_node, Tag)
                        else _empty_element("div")
                    ),
                    distributed_at=_selected_text(row.select_one(".colDistribue")),
                    view_url=_extract_anchor_url(title_anchor, base_url),
                    external_url=_extract_external_url(title_anchor),
                    file_name=file_name,
                    file_size=file_size,
                    is_new=row.select_one(".classeEtoileNouvDoc") is not None,
                )
            )

        categories.append(LeaDocumentCategory(title=title, items=items))

    return LeaDocumentsRes(
        page_title=page_title,
        course=course,
        instructions=instructions,
        printable_url=_extract_printable_url(soup, base_url),
        categories=categories,
    )


def _extract_submission(anchor: Tag | None, base_url: str) -> LeaAssignmentSubmission | None:
    if not isinstance(anchor, Tag):
        return None
    lines = _extract_lines(anchor)
    if not lines:
        return None
    label = " ".join(lines)
    file_name = lines[-1] if len(lines) > 1 else ""
    submitted_at = " ".join(lines[:-1]).removeprefix("Submitted ").strip() if len(lines) > 1 else ""
    return LeaAssignmentSubmission(
        label=label,
        submitted_at=submitted_at,
        file_name=file_name,
        download_url=_extract_anchor_url(anchor, base_url),
    )


def _extract_assignment_root(soup: BeautifulSoup) -> Tag | None:
    candidates = (
        "td.cvirContenuCVIR",
        "form#formUpload .container",
        "div.container",
    )
    for selector in candidates:
        node = soup.select_one(selector)
        if isinstance(node, Tag):
            return node
    return None


def _extract_assignment_detail_submission(
    root: Tag,
    base_url: str,
) -> list[LeaAssignmentSubmission]:
    submissions: list[LeaAssignmentSubmission] = []
    anchors = root.select("a[href*='ReadDepotEtudiant.aspx']")
    seen: set[str] = set()
    text_anchors = [
        anchor
        for anchor in anchors
        if isinstance(anchor, Tag) and _normalize_text(anchor.get_text(" ", strip=True))
    ]
    anchors_to_use = text_anchors or anchors
    for anchor in anchors_to_use:
        if not isinstance(anchor, Tag):
            continue
        download_url = _extract_anchor_url(anchor, base_url)
        if not download_url or download_url in seen:
            continue
        seen.add(download_url)
        file_name = _normalize_text(anchor.get_text(" ", strip=True))
        timestamp_node = anchor.find_next("span")
        submitted_at = ""
        if isinstance(timestamp_node, Tag):
            submitted_at = _normalize_text(timestamp_node.get_text(" ", strip=True)).strip("()")
        submissions.append(
            LeaAssignmentSubmission(
                label=file_name,
                submitted_at=submitted_at,
                file_name=file_name,
                download_url=download_url,
            )
        )
    return submissions


def _extract_lea_assignment_detail(
    container: Tag,
    soup: BeautifulSoup,
    base_url: str,
) -> LeaAssignmentContentRes:
    title = _selected_text(container.select_one("#lblTitre"))
    if not title:
        raise ValueError("Unable to locate the LEA assignment detail content in the HTML response")

    corrected_anchor = container.select_one("a[href*='ReadDepotCorrige.aspx'] + a[href*='ReadDepotCorrige.aspx']")
    if not isinstance(corrected_anchor, Tag):
        corrected_anchor = container.select_one("a[href*='ReadDepotCorrige.aspx']")
    linked_doc_anchor = container.select_one("#ALienFichierLie2")
    if not isinstance(linked_doc_anchor, Tag):
        linked_doc_anchor = container.select_one("a[href*='ReadDocumentTravail.aspx']")

    status_lines = _extract_lines(container.select_one("#trRemiseAutre"))
    item = LeaAssignmentItem(
        title=title,
        description=_selected_text(container.select_one("#lblEnonce")),
        linked_document_url=_extract_anchor_url(linked_doc_anchor, base_url),
        linked_document_name=_selected_text(linked_doc_anchor),
        status=" ".join(status_lines),
        corrected_copy_url=_extract_anchor_url(corrected_anchor, base_url),
        corrected_copy_name=_selected_text(corrected_anchor),
        deadline=_selected_text(container.select_one("#lblDateRemise")),
        submit_instructions=_selected_text(container.select_one("#lblRemiseInfo")),
        resubmit_instructions=_selected_text(container.select_one("#lblDeuxiemeRemise")),
        comment_instructions=_selected_text(container.select_one("#lblInstrucCommentaire")),
        upload_max_size=_selected_text(container.select_one("#lblTailleMax")),
        submissions=_extract_assignment_detail_submission(container, base_url),
    )

    general_instructions_parts = [
        _selected_text(container.select_one("#lblTitreInfoTravail")),
        _selected_text(container.select_one("#lblRemise")),
        _selected_text(container.select_one("#lblRemiseInfo")),
        _selected_text(container.select_one("#lblDeuxiemeRemise")),
    ]
    instructions = "\n".join(part for part in general_instructions_parts if part)

    return LeaAssignmentContentRes(
        page_title=_selected_text(container.select_one(".TitrePageLigne1")),
        course=_parse_course_context(_selected_text(container.select_one(".TitrePageLigne2"))),
        title=item.title,
        description=item.description,
        instructions=instructions,
        linked_document_url=item.linked_document_url,
        linked_document_name=item.linked_document_name,
        status=item.status,
        corrected_copy_url=item.corrected_copy_url,
        corrected_copy_name=item.corrected_copy_name,
        deadline=item.deadline,
        submit_instructions=item.submit_instructions,
        resubmit_instructions=item.resubmit_instructions,
        comment_instructions=item.comment_instructions,
        upload_max_size=item.upload_max_size,
        submissions=item.submissions,
        printable_url=_extract_printable_url(soup, base_url),
    )


def _extract_lea_assignment_list(
    container: Tag,
    soup: BeautifulSoup,
    base_url: str,
) -> LeaAssignmentsRes:
    
    page_title = _selected_text(container.select_one(".TitrePageLigne1"))
    course = _parse_course_context(_selected_text(container.select_one(".TitrePageLigne2")))
    instructions = _text_with_breaks(container.select_one(".CVIR_lblExplications"))

    items: list[LeaAssignmentItem] = []
    table = container.select_one("#tabListeTravEtu")
    if isinstance(table, Tag):
        row_container = table.find("tbody")
        for row in (row_container or table).find_all("tr", recursive=False):
            cells = row.find_all("td", recursive=False)
            if len(cells) < 4:
                continue

            title_anchor = cells[1].find("a")
            title_text = (
                _normalize_text(title_anchor.get_text(" ", strip=True))
                if isinstance(title_anchor, Tag)
                else ""
            )
            if not title_text:
                continue

            deadline_lines = _extract_lines(cells[2])
            submission_method = deadline_lines[1] if len(deadline_lines) > 1 else ""

            submissions: list[LeaAssignmentSubmission] = []
            corrected_copy_url: str | None = None
            status_cell = cells[3]
            nested_status_table = status_cell.find("table")
            if isinstance(nested_status_table, Tag):
                for nested_row in nested_status_table.find_all("tr", recursive=False):
                    nested_cells = nested_row.find_all("td", recursive=False)
                    if nested_cells:
                        submission = _extract_submission(
                            nested_cells[0].find("a", href=True), base_url
                        )
                        if submission is not None:
                            submissions.append(submission)
                        if corrected_copy_url is None and len(nested_cells) >= 3:
                            corrected_copy_url = _extract_anchor_url(
                                nested_cells[2].find("a", href=True), base_url
                            )

            items.append(
                LeaAssignmentItem(
                    title=title_text,
                    instruction_url=_extract_anchor_url(title_anchor, base_url),
                    deadline=deadline_lines[0] if deadline_lines else "",
                    submission_method=submission_method,
                    status=_normalize_text(status_cell.get_text(" ", strip=True)),
                    corrected_copy_url=corrected_copy_url,
                    submissions=submissions,
                    is_new=bool(cells[0].find("img")),
                )
            )

    return LeaAssignmentsRes(
        page_title=page_title,
        course=course,
        instructions=instructions,
        printable_url=_extract_printable_url(soup, base_url),
        assignments=items,
    )


def _extract_lea_assignments(html: str, base_url: str) -> LeaAssignmentsRes:
    soup = BeautifulSoup(html, "html.parser")
    container = _extract_assignment_root(soup)
    if not isinstance(container, Tag):
        raise ValueError("Unable to locate the LEA assignments content in the HTML response")

    if isinstance(container.select_one("#tabListeTravEtu"), Tag):
        return _extract_lea_assignment_list(container, soup, base_url)

    raise ValueError("Unable to recognize the LEA assignment list page structure in the HTML response")


def _extract_lea_assignment_content(html: str, base_url: str) -> LeaAssignmentContentRes:
    soup = BeautifulSoup(html, "html.parser")
    container = _extract_assignment_root(soup)
    if not isinstance(container, Tag):
        raise ValueError("Unable to locate the LEA assignment content in the HTML response")

    if isinstance(container.select_one("#lblTitre"), Tag):
        return _extract_lea_assignment_detail(container, soup, base_url)

    raise ValueError("Unable to recognize the LEA assignment detail page structure in the HTML response")


def _extract_grade_summary(table: Tag) -> list[LeaMetric]:
    metrics: list[LeaMetric] = []
    seen: set[tuple[str, str]] = set()
    for row in table.find_all("tr"):
        if not isinstance(row, Tag):
            continue
        cells = row.find_all("td", recursive=False)
        if len(cells) < 2:
            continue
        label = _normalize_text(cells[-2].get_text(" ", strip=True)).rstrip(":")
        value = _normalize_text(cells[-1].get_text(" ", strip=True))
        if not label or not value:
            continue
        key = (label, value)
        if key in seen:
            continue
        seen.add(key)
        metrics.append(LeaMetric(label=label, value=value))
    return metrics


def _text_after_bold(cell: Tag) -> str:
    working = BeautifulSoup(str(cell), "html.parser")
    for bold in working.find_all("b", recursive=True):
        bold.decompose()
    return _text_with_breaks(working)


def _extract_lea_grades(html: str, base_url: str) -> LeaGradesRes:
    soup = BeautifulSoup(html, "html.parser")
    header_container = soup.select_one(".centerPageLea")
    header_lines = _extract_lines(header_container)
    page_title = header_lines[0] if header_lines else _selected_text(soup.select_one(".titrePageLea"))
    course = _parse_course_context(header_lines[1] if len(header_lines) > 1 else "")

    note_wrapper = soup.select_one("table.note-wrapper")
    if not isinstance(note_wrapper, Tag):
        raise ValueError("Unable to locate the LEA grades content in the HTML response")

    metadata_cell = note_wrapper.find("td", attrs={"align": "RIGHT"})
    metadata_text = _selected_text(metadata_cell if isinstance(metadata_cell, Tag) else None)
    teacher_text = _normalize_text(
        (
            note_wrapper.find(
                string=lambda value: isinstance(value, str) and "Teacher:" in value
            )
            or ""
        )
    )
    teacher = teacher_text.removeprefix("Teacher:").strip()

    categories: list[LeaGradeCategory] = []
    table = note_wrapper.select_one("table.table-notes")
    current_category: LeaGradeCategory | None = None
    if isinstance(table, Tag):
        for row in table.find_all("tr"):
            if not isinstance(row, Tag):
                continue
            if row.find_parent("table") is not table:
                continue

            row_classes = set(row.get("class", []))
            if "tr-header-cat" in row_classes:
                header_cell = row.find("td")
                if not isinstance(header_cell, Tag):
                    continue
                title = _selected_text(header_cell.find("b"))
                if not title:
                    continue
                metrics = _extract_grade_summary(header_cell)
                note_text = _text_after_bold(header_cell)
                current_category = LeaGradeCategory(
                    title=title,
                    weight=next(
                        (metric.value for metric in metrics if metric.label == "Weight of this category"),
                        "",
                    ),
                    average=next(
                        (metric.value for metric in metrics if metric.label == "Your average for this category"),
                        "",
                    ),
                    note=note_text,
                )
                categories.append(current_category)
                continue

            cells = row.find_all("td", recursive=False)
            if len(cells) < 6 or current_category is None:
                continue

            title_cell = cells[2]
            title = _selected_text(title_cell.find("b"))
            index = _normalize_text(cells[1].get_text(" ", strip=True))
            if not title or not index:
                continue

            mark_lines = _extract_lines(cells[3])
            weight_lines = _extract_lines(cells[5])
            note = _text_after_bold(title_cell)
            current_category.assessments.append(
                LeaGradeAssessment(
                    index=index,
                    title=title,
                    note=note,
                    mark=mark_lines[0] if mark_lines else "",
                    percentage=mark_lines[1] if len(mark_lines) > 1 else "",
                    class_average=_normalize_text(cells[4].get_text(" ", strip=True)),
                    weight=weight_lines[0] if weight_lines else "",
                    weighted_points=weight_lines[1] if len(weight_lines) > 1 else "",
                    discarded="discarded" in note.lower(),
                )
            )

    summary_table = note_wrapper.select_one("table.tb-sommaire")
    summary = _extract_grade_summary(summary_table) if isinstance(summary_table, Tag) else []

    return LeaGradesRes(
        page_title=page_title,
        course=course,
        snapshot=metadata_text,
        teacher=teacher,
        printable_url=_extract_printable_url(soup, base_url),
        summary_link=_extract_anchor_url(soup.select_one("a.lienRetourSommaire"), base_url),
        summary=summary,
        categories=categories,
    )


def _extract_announcement_title(title_cell: Tag) -> str:
    texts: list[str] = []
    for child in title_cell.children:
        if isinstance(child, Tag) and "TitreCoursGroupe" in child.get("class", []):
            break
        if isinstance(child, NavigableString):
            normalized = _normalize_text(str(child))
            if normalized:
                texts.append(normalized)
        elif isinstance(child, Tag):
            normalized = _normalize_text(child.get_text(" ", strip=True))
            if normalized:
                texts.append(normalized)
    return " ".join(texts).strip()


def _extract_announcement_course(course_node: Tag | None) -> tuple[LeaCourseContext, str, str]:
    lines = _extract_lines(course_node)
    course = _parse_course_context(lines[0]) if lines else LeaCourseContext()

    published_by = ""
    published_on = ""
    title_parts: list[str] = []
    for line in lines:
        match = _PUBLISHED_PATTERN.match(line)
        if match:
            published_by = match.group(1).strip()
            published_on = match.group(2).strip()
            break
        if line != lines[0]:
            title_parts.append(line)

    if title_parts and not course.course_title:
        course.course_title = _normalize_text(" ".join(title_parts))
    elif title_parts:
        course.course_title = _normalize_text(" ".join(title_parts))

    if len(lines) >= 2 and course.course_title:
        course.header = _normalize_text(f"{lines[0]} {course.course_title}")
    elif lines:
        course.header = lines[0]
    return course, published_by, published_on


def _extract_lea_announcement(html: str, base_url: str) -> LeaAnnouncementRes:
    soup = BeautifulSoup(html, "html.parser")
    title_cell = soup.select_one("td.TitreAnnonce")
    content_cell = soup.select_one("td.Contenu")
    if not isinstance(title_cell, Tag) or not isinstance(content_cell, Tag):
        raise ValueError("Unable to locate the LEA announcement content in the HTML response")

    course_node = title_cell.select_one(".TitreCoursGroupe")
    course, published_by, published_on = _extract_announcement_course(course_node)

    return LeaAnnouncementRes(
        title=_extract_announcement_title(title_cell),
        course=course,
        published_by=published_by,
        published_on=published_on,
        content=_text_with_breaks(content_cell),
        printable_url=_extract_printable_url(soup, base_url),
    )


async def get_lea_documents(req: LeaLinkReq) -> LeaDocumentsRes:
    response = await _fetch_response(req.link)
    return _extract_lea_documents(response.text, str(response.url))


async def get_lea_assignments(req: LeaLinkReq) -> LeaAssignmentsRes:
    response = await _fetch_response(req.link)
    return _extract_lea_assignments(response.text, str(response.url))


async def get_lea_assignment_content(req: LeaLinkReq) -> LeaAssignmentContentRes:
    response = await _fetch_response(req.link)
    return _extract_lea_assignment_content(response.text, str(response.url))


async def get_lea_grades(req: LeaLinkReq) -> LeaGradesRes:
    response = await _fetch_response(req.link)
    return _extract_lea_grades(response.text, str(response.url))


async def get_lea_announcement(req: LeaLinkReq) -> LeaAnnouncementRes:
    response = await _fetch_response(req.link)
    return _extract_lea_announcement(response.text, str(response.url))
