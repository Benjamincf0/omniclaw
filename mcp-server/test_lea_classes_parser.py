import sys
import unittest
from pathlib import Path

# Ensure the mcp-server root is on sys.path when running the file directly
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from models.lea_classes import _extract_lea_classes  # noqa: E402


FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "lea_classes_fixture.html"


class LeaClassesParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.html = FIXTURE_PATH.read_text(encoding="utf-8")
        self.classes = _extract_lea_classes(
            self.html,
            "https://johnabbott-lea.omnivox.ca/cvir/doce/Default.aspx",
        )

    def test_extracts_class_headers_and_sections(self) -> None:
        self.assertEqual(len(self.classes), 2)

        stats = self.classes[0]
        self.assertEqual(stats.course_code, "201-DDD-05")
        self.assertEqual(stats.course_title, "STATISTICS")
        self.assertEqual(stats.section, "00003")
        self.assertEqual(stats.schedule, "Mon 10:00, Wed 10:30, Thu 10:00")
        self.assertEqual(stats.teacher, "Luiz Kazuo Takei")
        self.assertEqual(
            [section.title for section in stats.sections],
            [
                "Documents and videos",
                "Assignments",
                "Evaluation grades",
                "Announcements",
            ],
        )

    def test_extracts_metrics_announcements_and_status(self) -> None:
        stats = self.classes[0]
        documents = stats.sections[0]
        self.assertEqual(
            [(metric.label, metric.value) for metric in documents.metrics],
            [
                ("Distributed documents", "30"),
                ("New documents", "3"),
            ],
        )
        announcements = stats.sections[3]
        self.assertEqual(len(announcements.announcements), 2)
        self.assertEqual(announcements.announcements[0].date, "May 16")
        self.assertEqual(announcements.announcements[0].title, "Extra Office Hours")
        self.assertTrue(
            announcements.announcements[0].url.endswith("/cvir/comm/Communique.aspx?foo=1")
        )

        physics = self.classes[1]
        events = physics.sections[0]
        forum = physics.sections[1]
        self.assertEqual(events.summary, "coming month")
        self.assertEqual(forum.status, "Not enabled")


if __name__ == "__main__":
    unittest.main()
