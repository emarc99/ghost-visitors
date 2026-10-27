"""Marigold Bakery: a tiny shop for the ghosts to haunt.

In "broken" mode it carries five planted problems that real sites ship every day.
In "fixed" mode the same pages have none of them, so any complaint there is a
false alarm. That pair is what the eval measures against.
"""

import time

from flask import Flask, redirect, render_template_string, request, url_for

PLANTED = {
    "slow_load": "A render-blocking script delays the first page by about 3 seconds.",
    "horizontal_scroll": "The page is a fixed 980px wide, so phones scroll sideways.",
    "unnamed_control": "The email field has only placeholder text, no label.",
    "small_tap_target": "The quantity - and + buttons are 16px squares.",
    "not_keyboard_reachable": "'Place order' is a clickable div that a keyboard can't reach.",
    "low_contrast": "Body text is light grey on white.",
    "small_text": "Body text is 11px.",
}

BREADS = [
    ("pan-de-muerto", "Pan de muerto", "Orange-blossom sweet bread with bone-shaped crosses.", 6),
    ("conchas", "Marigold conchas", "Soft shell buns dusted with cempasúchil sugar.", 4),
    ("calaveras", "Sugar calaveras", "Hand-decorated sugar skulls for the ofrenda.", 3),
]

BASE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }} · Marigold Bakery</title>
{% if broken and slow %}<script src="{{ url_for('slow_script') }}"></script>{% endif %}
<style>
  * { box-sizing: border-box; }
  body { margin: 0; font-family: Georgia, serif; background: #fffaf0; }
  header { background: #7c2d12; color: #fff7ed; padding: 16px 24px; }
  header a { color: #fde68a; }
  header a, .card a { display: inline-block; padding: 10px 6px; }
  .card { background: #fff; border: 1px solid #fed7aa; border-radius: 8px; padding: 16px; margin: 12px 0; }
  h1, h2 { color: #7c2d12; }
  label { display: block; margin-top: 12px; font-weight: bold; }
  input, select { font-size: 16px; padding: 8px; width: 100%; max-width: 320px; }
  .qty { display: flex; align-items: center; gap: 8px; }
  .qty input { width: 64px; text-align: center; }
  .submit { display: inline-block; margin-top: 16px; background: #c2410c; color: #fff; border: 0;
            border-radius: 6px; padding: 12px 20px; font-size: 18px; cursor: pointer; }
{% if broken %}
  .page { width: 980px; margin: 0 auto; padding: 24px; }
  p, li, .muted { font-size: 11px; color: #a3a3a3; }
  .qty button { width: 16px; height: 16px; padding: 0; font-size: 10px; line-height: 1; }
{% else %}
  .page { max-width: 760px; margin: 0 auto; padding: 24px; }
  p, li, .muted { font-size: 17px; color: #3f3f46; }
  .qty button { width: 44px; height: 44px; font-size: 20px; }
{% endif %}
</style>
</head>
<body>
<header><strong>Marigold Bakery</strong> · <a href="{{ url_for('home') }}">Breads</a> · <a href="{{ url_for('order') }}">Order</a></header>
<main class="page">
{{ body|safe }}
</main>
</body>
</html>"""

HOME = """
<h1>Bread for your ofrenda</h1>
<p>Every year we bake for the families who set a place for the ones they miss. Order by
October 31 and pick up fresh on November 1 or 2.</p>
{% for slug, name, blurb, price in breads %}
<div class="card">
  <h2>{{ name }}</h2>
  <p>{{ blurb }}</p>
  <p class="muted">${{ price }} each</p>
  <a href="{{ url_for('order', item=slug) }}">Order {{ name }}</a>
</div>
{% endfor %}
"""

ORDER = """
<h1>Order</h1>
<p>Tell us what to bake and when you'll come by.</p>
<form method="post" action="{{ url_for('order') }}" id="order-form">
  <label for="item">Bread</label>
  <select id="item" name="item">
  {% for slug, name, blurb, price in breads %}
    <option value="{{ slug }}" {% if slug == item %}selected{% endif %}>{{ name }} (${{ price }})</option>
  {% endfor %}
  </select>

  <label for="name">Your name</label>
  <input id="name" name="name" autocomplete="name" required>

  {% if broken %}
  <input id="email" name="email" type="email" placeholder="Email" style="margin-top:12px" required>
  {% else %}
  <label for="email">Email</label>
  <input id="email" name="email" type="email" autocomplete="email" required>
  {% endif %}

  <label for="day">Pickup day</label>
  <select id="day" name="day">
    <option>November 1</option>
    <option>November 2</option>
  </select>

  <label for="qty">How many</label>
  <div class="qty">
    <button type="button" aria-label="One fewer" onclick="step(-1)">-</button>
    <input id="qty" name="qty" type="number" min="1" max="24" value="1">
    <button type="button" aria-label="One more" onclick="step(1)">+</button>
  </div>

  {% if broken %}
  <div class="submit" onclick="document.getElementById('order-form').requestSubmit()">Place order</div>
  {% else %}
  <button class="submit" type="submit">Place order</button>
  {% endif %}
</form>
<script>
function step(n) {
  const q = document.getElementById('qty');
  q.value = Math.min(24, Math.max(1, (parseInt(q.value, 10) || 1) + n));
}
</script>
"""

THANKS = """
<h1>Thank you, {{ name }}</h1>
<p>We'll have {{ qty }} × {{ bread }} ready on {{ day }}. A confirmation is on its way to {{ email }}.</p>
<a href="{{ url_for('home') }}">Back to the breads</a>
"""


def create_app(mode: str = "broken") -> Flask:
    if mode not in ("broken", "fixed"):
        raise ValueError("mode must be 'broken' or 'fixed'")
    app = Flask(__name__)
    broken = mode == "broken"
    names = {slug: name for slug, name, _, _ in BREADS}

    def page(title: str, body: str, slow: bool = False, **ctx) -> str:
        inner = render_template_string(body, breads=BREADS, broken=broken, **ctx)
        return render_template_string(BASE, title=title, body=inner, broken=broken, slow=slow)

    @app.get("/")
    def home():
        return page("Breads", HOME, slow=True)

    @app.route("/order", methods=["GET", "POST"])
    def order():
        if request.method == "POST":
            return redirect(url_for(
                "thanks",
                name=request.form.get("name", ""),
                email=request.form.get("email", ""),
                item=request.form.get("item", ""),
                day=request.form.get("day", ""),
                qty=request.form.get("qty", "1"),
            ))
        return page("Order", ORDER, item=request.args.get("item", ""))

    @app.get("/thanks")
    def thanks():
        args = request.args
        return page("Thank you", THANKS, name=args.get("name", "friend"), email=args.get("email", ""),
                    bread=names.get(args.get("item", ""), "bread"), day=args.get("day", ""),
                    qty=args.get("qty", "1"))

    @app.get("/slow.js")
    def slow_script():
        time.sleep(3)
        return "/* the bakery's analytics, taking its time */", 200, {"Content-Type": "text/javascript"}

    return app


if __name__ == "__main__":
    import sys

    create_app(sys.argv[1] if len(sys.argv) > 1 else "broken").run(port=8001)
