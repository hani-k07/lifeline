import pytest
from streamlit.testing.v1 import AppTest

from lifeline.constants import BLOOD_GROUPS
from lifeline.ui import components as c
from lifeline.ui import tokens as t
from lifeline.ui.theme import css, variables


# ------------------------------------------------------------------ escaping + markup
def test_user_text_is_escaped_but_generated_markup_is_not():
    assert c.esc("<script>alert(1)</script>") == "&lt;script&gt;alert(1)&lt;/script&gt;"
    assert c.esc(c.Html("<b>ok</b>")) == "<b>ok</b>"
    assert c.esc(None) == "" and c.esc(5) == "5"
    card = c.kpi_card("<img src=x onerror=1>", "<b>9</b>", hint="<i>h</i>")
    assert "<img" not in card and "&lt;img" in card and "<b>9</b>" not in card


def test_generated_html_has_no_blank_lines_or_indentation():
    """A blank line ends a Markdown HTML block and indented lines become a code block (the bug that leaked <div> text)."""
    for markup in (c.kpi_card("A", 1, hint="x"), c.stock_grid({"A+": 3}), c.html_table([{"a": 1}], [c.Col("A", "a")], "cap"),
                   c.alert_html("m", "danger"), c.row_list([("a", "b")])):
        assert "\n\n" not in markup and not any(line.startswith(" ") for line in markup.splitlines())


def test_every_blood_group_badge_prints_its_label_and_negative_is_outlined():
    for group in BLOOD_GROUPS:
        badge = c.blood_group_badge(group)
        assert f">{group}</span>" in badge
        assert ("Rh positive" in badge) == group.endswith("+")
    assert "background:transparent" not in c.blood_group_badge("O-")
    assert c.blood_group_badge("O+", 12).count("12u") == 1
    assert "Q?" in c.blood_group_badge("Q?")                      # unknown labels degrade to plain text, never crash


@pytest.mark.parametrize(
    ("status", "kind"),
    [("CRITICAL", "danger"), ("SEVERE", "danger"), ("DEFER", "warning"), ("SAFE", "success"), ("NONE", "success"),
     ("PENDING", "info"), ("CANCELLED", "neutral"), ("weird", "neutral")],
)
def test_status_pill_kind_and_glyph(status, kind):
    pill = c.status_pill(status)
    assert c.MARKS[kind] in pill and status.upper().replace("_", " ") in pill.upper()


def test_status_words_are_not_conveyed_by_colour_alone():
    marks = {kind: c.MARKS[kind] for kind in c.MARKS}
    assert len(set(marks.values())) == len(marks)                 # a different glyph per meaning


def test_alert_roles_and_titles():
    assert 'role="alert"' in c.alert_html("m", "danger") and 'role="alert"' in c.alert_html("m", "warning")
    assert 'role="status"' in c.alert_html("m", "success") and "Problem:" in c.alert_html("m", "danger")
    assert "Custom:" in c.alert_html("m", "info", title="Custom")


def test_stock_grid_levels_and_text_cues():
    grid = c.stock_grid({"A+": 0, "A-": 5, "B+": 30})
    assert grid.count('class="ll-stock ') == 8
    assert "critical" in grid and "low" in grid and "ok" in grid
    assert "CRITICAL" in grid and "LOW" in grid and "OK" in grid  # the level is also written out
    assert 'aria-label="30 units, ok"' in grid


def test_step_indicator_marks_progress():
    def app():
        from lifeline.ui import components as ui

        ui.steps(["Patient", "Sources", "Confirm"], current=2)

    at = AppTest.from_function(app).run()
    html = " ".join(m.value for m in at.markdown)
    assert html.count("ll-step done") == 1 and html.count("ll-step active") == 1 and 'aria-current=step' in html


# ------------------------------------------------------------------ table logic
ROWS = [{"name": "Zara", "units": 5}, {"name": "ali", "units": 12}, {"name": "Bilal", "units": 5}, {"name": None, "units": None},
        {"name": "Mayo", "units": 30}]
COLS = [c.Col("Name", "name"), c.Col("Units", "units", align="right")]


def test_table_search_is_case_insensitive_over_searchable_columns():
    assert [r["name"] for r in c.table_view(ROWS, COLS, query="AL").rows] == ["ali", "Bilal"]
    assert c.table_view(ROWS, COLS, query="nope").total == 0
    no_search = [c.Col("Name", "name", search=False), c.Col("Units", "units")]
    assert c.table_view(ROWS, no_search, query="ali").total == 0


def test_table_sort_is_stable_case_insensitive_and_puts_missing_last():
    asc = [r["name"] for r in c.table_view(ROWS, COLS, sort_field="name").rows]
    assert asc == ["ali", "Bilal", "Mayo", "Zara", None]
    by_units = [r["name"] for r in c.table_view(ROWS, COLS, sort_field="units").rows]
    assert by_units[:2] == ["Zara", "Bilal"] and by_units[-1] is None            # equal units keep their original order
    desc = [r["units"] for r in c.table_view(ROWS, COLS, sort_field="units", descending=True).rows]
    assert desc[:4] == [30, 12, 5, 5]


def test_table_pagination_clamps_and_counts_pages():
    rows = [{"n": i} for i in range(25)]
    cols = [c.Col("N", "n")]
    v = c.table_view(rows, cols, page=2, page_size=10)
    assert (v.page, v.pages, v.total, len(v.rows)) == (2, 3, 25, 10) and v.rows[0]["n"] == 10
    assert c.table_view(rows, cols, page=99, page_size=10).page == 3          # clamped
    assert c.table_view(rows, cols, page=-4, page_size=10).page == 1
    assert c.table_view([], cols).pages == 1 and c.table_view([], cols).rows == []


def test_html_table_escapes_cells_and_allows_trusted_renderers():
    rows = [{"n": "<b>x</b>", "g": "A+"}]
    table = c.html_table(rows, [c.Col("N", "n"), c.Col("G", "g", render=lambda v, r: c.blood_group_badge(v))])
    assert "&lt;b&gt;x&lt;/b&gt;" in table and "<b>x</b>" not in table and 'class="ll-badge"' in table
    assert "—" in c.html_table([{"n": None}], [c.Col("N", "n")])              # missing value shows a dash


# ------------------------------------------------------------------ widgets through AppTest
def test_data_table_widget_search_sort_and_paging():
    def app():
        from lifeline.ui import components as ui

        rows = [{"name": f"Donor {i:02d}", "n": i} for i in range(30)]
        ui.data_table(rows, [ui.Col("Name", "name"), ui.Col("N", "n", align="right")], key="t", page_size=10)

    at = AppTest.from_function(app).run()
    assert not at.exception
    page = " ".join(m.value for m in at.markdown)
    assert "Donor 00" in page and "Donor 10" not in page and "Page 1 of 3" in page
    next(b for b in at.button if b.label == "Next ›").click()
    at.run()
    assert "Donor 10" in " ".join(m.value for m in at.markdown) and "Page 2 of 3" in " ".join(m.value for m in at.markdown)
    at.text_input(key="t:q").set_value("donor 2")
    at.run()
    body = " ".join(m.value for m in at.markdown)
    assert "Donor 25" in body and "Donor 05" not in body


def test_empty_table_shows_an_empty_state_not_a_blank():
    def app():
        from lifeline.ui import components as ui

        ui.data_table([], [ui.Col("A", "a")], key="e", empty_title="No donors yet", empty_body="Register one to start.")

    at = AppTest.from_function(app).run()
    assert not at.exception and "No donors yet" in " ".join(m.value for m in at.markdown)


def test_confirm_dialog_needs_two_clicks_and_cancel_resets():
    def app():
        import streamlit as st

        from lifeline.ui import components as ui

        if ui.confirm_dialog("del", "Delete it", "Really delete?", confirm_label="Yes, delete", danger=True):
            st.session_state["done"] = st.session_state.get("done", 0) + 1

    at = AppTest.from_function(app).run()
    assert "done" not in at.session_state
    next(b for b in at.button if b.label == "Delete it").click()
    at.run()
    assert any("Really delete?" in m.value for m in at.markdown) and "done" not in at.session_state
    next(b for b in at.button if b.label == "Cancel").click()
    at.run()
    assert any(b.label == "Delete it" for b in at.button) and "done" not in at.session_state       # back to the first state
    next(b for b in at.button if b.label == "Delete it").click()
    at.run()
    next(b for b in at.button if b.label == "Yes, delete").click()
    at.run()
    assert at.session_state["done"] == 1                                                            # fired exactly once
    assert any(b.label == "Delete it" for b in at.button)


def test_ai_panel_is_always_labelled_advisory_and_escaped():
    def app():
        from lifeline.ui import components as ui

        ui.ai_panel("Give <b>2 units</b>")

    at = AppTest.from_function(app).run()
    text = " ".join(m.value for m in at.markdown)
    assert "AI suggestion — verify clinically" in text and "&lt;b&gt;2 units&lt;/b&gt;" in text and "<b>2 units</b>" not in text


# ------------------------------------------------------------------ theme
@pytest.mark.parametrize("theme", ["dark", "light"])
def test_stylesheet_is_fully_substituted_and_uses_the_brand_tokens(theme):
    out = css(theme)
    assert "$" not in out and "None" not in out
    p = t.palette(theme)
    assert p.bg_base in out and p.button in out and f"color-scheme: {theme}" in out
    assert variables(theme)["danger_text"] and variables(theme)["neutral_bg"]


def test_sparse_use_of_blur():
    """The brief asks for at most one subtle blur layer."""
    assert css("dark").count("backdrop-filter") == 1
