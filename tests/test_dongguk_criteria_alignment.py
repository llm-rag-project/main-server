import unittest

from app.api.v1.reports import (
    DonggukMailArticle,
    _is_buddhism_mail_eligible,
    _is_education_mail_eligible,
    _is_foundation_mail_eligible,
    _dongguk_mail_section_policy,
    _normalize_dongguk_priority_criteria,
)
from scripts.compare_hongbo_original_vs_ai import TOPIC_METHOD, score_pair


class DonggukCriteriaAlignmentTest(unittest.TestCase):
    def test_legacy_direct_relation_rules_become_section_specific(self):
        criteria = """우선순위 기준:
- 대학 정책과 고등교육 일반 이슈는 동국대학교와의 직접 관련성을 확인해 선정합니다.
- 불교계와 종단 일반 소식은 동국대학교와 직접 연결될 때만 참고 기사로 선정합니다.

제외 기준:
- 동국대학교와 직접 관련성이 확인되지 않는 기사는 제외합니다.
- 동국대의 인사발령 관련 기사는 모두 제외합니다.
- 동국대학교 경주캠퍼스 관련 주제는 모두 제외합니다."""

        normalized = _normalize_dongguk_priority_criteria(criteria)

        self.assertIn("대학 [교육] 섹션은 동국대 직접 언급 여부와 관계없이", normalized)
        self.assertIn("불교 [종단] 섹션은 동국대 직접 언급 여부와 관계없이", normalized)
        self.assertIn("동국대 [법인/건학위] 섹션에서", normalized)
        self.assertIn("인사발령 관련 기사는 모두 제외", normalized)
        self.assertIn("경주캠퍼스 관련 주제는 모두 제외", normalized)

    def test_affiliated_research_units_are_foundation_articles(self):
        articles = [
            DonggukMailArticle(
                title="[불교학술원] 석전·만해의 수행과 교육철학 조명",
                section="dongguk_core",
            ),
            DonggukMailArticle(
                title="[현정환 교수 인터뷰] 전자 결제 대행 감독 강화해야",
                section="dongguk_core",
            ),
            DonggukMailArticle(
                title="지역미래불자장학 101호 기부",
                section="dongguk_core",
            ),
        ]

        self.assertTrue(all(_is_foundation_mail_eligible(article) for article in articles))

    def test_summary_and_classification_can_prove_foundation_affiliation(self):
        articles = [
            DonggukMailArticle(
                title="법장대종사 보살행 조명할 학술 토론의 장",
                summary="동국대 불교학술원이 학술대회를 개최한다.",
                section="dongguk_core",
                category="학술활동",
            ),
            DonggukMailArticle(
                title="동문 4인 기획전 개최",
                section="dongguk_core",
                category="동문/교수 인터뷰·칼럼",
            ),
        ]

        self.assertTrue(all(_is_foundation_mail_eligible(article) for article in articles))

    def test_ai_selected_article_is_kept_before_backend_top_up(self):
        subjects = [
            "동국대 장학기금 전달식 개최",
            "동국대 양자소자 특허 기술 개발",
            "동국대 연극영화학과 국제상 수상",
            "동국대 총장 고등교육 기조연설",
            "동국대 박물관 불교미술 전시 개막",
            "동국대 지역기업 산학협력 협약 체결",
            "동국대 동문 작가 현대미술 개인전",
        ]
        candidates = [
            DonggukMailArticle(
                id=index,
                title=title,
                summary=title,
                section="dongguk_core",
                category="학교 공식 행사",
                score=100 - index,
            )
            for index, title in enumerate(subjects, start=1)
        ]
        ai_selected = [candidates[-1]]

        selected, _ = _dongguk_mail_section_policy(
            ai_selected,
            [],
            candidates,
            "2026-07-15",
        )

        self.assertIn(7, [article.id for article in selected])
        self.assertEqual(len(selected), 4)

    def test_reference_sections_do_not_require_dongguk_name(self):
        education = DonggukMailArticle(
            title="교육부, 고등교육재정교부금법 개편 논의",
            section="education",
        )
        buddhism = DonggukMailArticle(
            title="조계종, 신임 원로의원 선출",
            section="buddhism",
        )

        self.assertTrue(_is_education_mail_eligible(education))
        self.assertTrue(_is_buddhism_mail_eligible(buddhism))

    def test_education_section_rejects_k12_policy_without_higher_education_context(self):
        article = DonggukMailArticle(
            title="교육부, 폐교 활용도 높이고 학교 시설 개방 늘린다",
            summary="초중고 폐교와 학교 시설을 지역사회에 개방하는 정책이다.",
            section="education",
        )

        self.assertFalse(_is_education_mail_eligible(article))

    def test_education_section_accepts_higher_education_policy(self):
        article = DonggukMailArticle(
            title="교육부, 고등교육 재정과 대학 등록금 제도 개편 논의",
            section="education",
        )

        self.assertTrue(_is_education_mail_eligible(article))

    def test_buddhism_section_accepts_temple_and_hermitage_news(self):
        article = DonggukMailArticle(
            title="백양사·산내 암자까지 명승으로 확대해 품는다",
            source="법보신문",
            section="buddhism",
        )

        self.assertTrue(_is_buddhism_mail_eligible(article))

    def test_unrelated_foundation_article_stays_ineligible(self):
        article = DonggukMailArticle(
            title="외부 기업 신제품 출시 행사",
            section="dongguk_core",
        )
        self.assertFalse(_is_foundation_mail_eligible(article))

    def test_same_event_with_different_headline_is_topic_match(self):
        original = {
            "section": "foundation",
            "title": "더 젊어진 연등회, 대학 불교동아리 적극 참여",
        }
        selected = {
            "section": "dongguk_core",
            "title": "[포토] 2025 연등회 참가한 동국대 불교동아리들",
        }

        score, method = score_pair(original, selected)

        self.assertGreaterEqual(score, 0.58)
        self.assertEqual(method, TOPIC_METHOD)


if __name__ == "__main__":
    unittest.main()
