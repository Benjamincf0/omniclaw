import sys
import unittest
from pathlib import Path

# Ensure the mcp-server root is on sys.path when running the file directly
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from models.lea_details import (  # noqa: E402
    _extract_lea_assignment_content,
    _extract_lea_announcement,
    _extract_lea_assignments,
    _extract_lea_documents,
    _extract_lea_grades,
)


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


class LeaDetailParserTests(unittest.TestCase):
    def test_extracts_documents_and_videos(self) -> None:
        html = (FIXTURE_DIR / "lea_documents_detail_fixture.html").read_text(encoding="utf-8")
        result = _extract_lea_documents(
            html,
            "https://johnabbott-lea.omnivox.ca/cvir/ddle/ListeDocuments.aspx",
        )

        self.assertEqual(result.page_title, "Distributed Documents and Videos")
        self.assertEqual(result.course.course_code, "201-DDB-05")
        self.assertEqual(result.course.course_title, "CALCULUS III")
        self.assertEqual(result.course.section, "00003")
        self.assertIn("consult or download them below", result.instructions)
        self.assertTrue(result.printable_url and "FormatAffichage=1" in result.printable_url)

        self.assertEqual(len(result.categories), 2)
        self.assertEqual(result.categories[0].title, "Course Materials")
        self.assertEqual(result.categories[0].items[0].title, "Power Series Review")
        self.assertEqual(result.categories[0].items[0].distributed_at, "since Jan 21, 2024")

        solutions = next(category for category in result.categories if category.title == "Solutions")
        self.assertTrue(solutions.items[0].is_new)
        self.assertEqual(
            solutions.items[0].title,
            "Typed solutions to Quiz 1 (other section's version)",
        )
        self.assertEqual(solutions.items[0].external_url, "https://www.overleaf.com/read/jfdxhfnrfcjw#534df2")

    def test_extracts_assignments(self) -> None:
        html = (FIXTURE_DIR / "lea_assignments_detail_fixture.html").read_text(encoding="utf-8")
        result = _extract_lea_assignments(
            html,
            "https://johnabbott-lea.omnivox.ca/cvir/dtrv/ListeTravauxEtu.aspx",
        )

        self.assertEqual(result.page_title, "List of assignments")
        self.assertEqual(result.course.course_code, "201-DDD-05")
        self.assertEqual(result.course.course_title, "STATISTICS")
        self.assertEqual(result.course.section, "00003")
        self.assertIn("Submit your assignment", result.instructions)
        self.assertTrue(result.printable_url and "FormatAffichage=1" in result.printable_url)

        self.assertEqual(len(result.assignments), 2)
        first = result.assignments[0]
        self.assertEqual(first.title, "Project - Part 1 - Code")
        self.assertTrue(first.instruction_url and "DepotTravail.aspx" in first.instruction_url)
        self.assertEqual(first.deadline, "Apr-12, 2024 at 23:55")
        self.assertEqual(first.submission_method, "via Léa")
        self.assertEqual(len(first.submissions), 2)
        self.assertEqual(first.submissions[0].file_name, "ming_li_liu.r")
        self.assertTrue(first.submissions[0].download_url and "ReadDepotEtudiant.aspx" in first.submissions[0].download_url)

        second = result.assignments[1]
        self.assertEqual(second.title, "Project - Part 1 - Report")
        self.assertTrue(second.corrected_copy_url and "ReadDepotCorrige.aspx" in second.corrected_copy_url)

    def test_extracts_assignment_content_popup(self) -> None:
        html = (FIXTURE_DIR / "lea_assignment_content_fixture.html").read_text(encoding="utf-8")
        result = _extract_lea_assignment_content(
            html,
            "https://johnabbott-lea.omnivox.ca/cvir/dtrv/DepotTravail.aspx?idtravail=lab2",
        )

        self.assertEqual(result.page_title, "Assignment instructions and submittal")
        self.assertEqual(result.course.course_code, "420-DBF-03")
        self.assertEqual(result.course.course_title, "INTRODUCTION TO PROGRAMMING IN C")
        self.assertEqual(result.course.section, "00001")
        self.assertEqual(result.title, "Lab 2")
        self.assertEqual(result.description, ":^)")
        self.assertEqual(result.linked_document_name, "Lab_2_-_DBF.pdf")
        self.assertTrue(result.linked_document_url and "ReadDocumentTravail.aspx" in result.linked_document_url)
        self.assertEqual(result.status, "You have submitted this assignment")
        self.assertEqual(result.corrected_copy_name, "Correction_Lab_2.pdf")
        self.assertTrue(result.corrected_copy_url and "ReadDepotCorrige.aspx" in result.corrected_copy_url)
        self.assertEqual(result.deadline, "Thursday March 21 2024")
        self.assertIn("ZIP format", result.submit_instructions)
        self.assertIn("additional file", result.resubmit_instructions)
        self.assertEqual(result.upload_max_size, "Maximum size 200 MB")
        self.assertIn("communicate to your teacher", result.comment_instructions)
        self.assertEqual(len(result.submissions), 1)
        self.assertEqual(result.submissions[0].file_name, "lab2.zip")
        self.assertEqual(result.submissions[0].submitted_at, "Mar 19, 2024 at 15:26")
        self.assertTrue(result.submissions[0].download_url and "ReadDepotEtudiant.aspx" in result.submissions[0].download_url)

    def test_extracts_grades(self) -> None:
        html = (FIXTURE_DIR / "lea_grades_detail_fixture.html").read_text(encoding="utf-8")
        result = _extract_lea_grades(
            html,
            "https://johnabbott-lea.omnivox.ca/cvir/note/ListeEvalCVIR.ovx",
        )

        self.assertEqual(result.page_title, "Detailed marks per assessment")
        self.assertEqual(result.course.course_code, "201-DDD-05")
        self.assertEqual(result.course.course_title, "Statistics")
        self.assertEqual(result.course.section, "00003")
        self.assertEqual(result.teacher, "Luiz Kazuo Takei")
        self.assertIn("Assessment Marks", result.snapshot)
        self.assertTrue(result.summary_link and "Go to the grades summary" not in result.summary_link)

        metrics = {metric.label: metric.value for metric in result.summary}
        self.assertEqual(metrics["Current grade"], "101.3/100 101%")
        self.assertEqual(metrics["Projection of your final grade"], "100%")
        self.assertEqual(metrics["Final grade transmitted"], "100%")
        self.assertEqual(metrics["Final class average"], "86%")

        self.assertGreaterEqual(len(result.categories), 4)
        self.assertEqual(result.categories[0].title, "Exams")
        self.assertEqual(result.categories[0].weight, "30% of final grade")
        self.assertEqual(result.categories[0].assessments[0].title, "T1")
        self.assertEqual(result.categories[0].assessments[0].percentage, "96.15%")

        quizzes = next(category for category in result.categories if category.title == "Quizzes")
        discarded = next(assessment for assessment in quizzes.assessments if assessment.title == "Q2")
        self.assertTrue(discarded.discarded)

    def test_extracts_announcement_popup(self) -> None:
        html = (FIXTURE_DIR / "lea_announcement_fixture.html").read_text(encoding="utf-8")
        result = _extract_lea_announcement(
            html,
            "https://johnabbott-lea.omnivox.ca/cvir/comm/Communique.aspx",
        )

        self.assertEqual(result.title, "Final Grade Submissions")
        self.assertEqual(result.course.course_code, "603-200-AB")
        self.assertEqual(result.course.course_title, "Marginality and Representation (Blended)")
        self.assertEqual(result.course.section, "00001")
        self.assertEqual(result.published_by, "Brian Mitchell Peters")
        self.assertEqual(result.published_on, "May 20th, 2024")
        self.assertIn("Hi everyone.", result.content)
        self.assertIn("Thank you :)", result.content)
        self.assertTrue(result.printable_url and "impr=1" in result.printable_url)


if __name__ == "__main__":
    unittest.main()
