// bulu-api: 2bulu 深圳约伴数据的 HTTP 接口，数据直接查 D1 (2bulu-activities)。
//
// 路由:
//   GET /api/meta                        -> {count, upcoming_count, generated_at}
//   GET /api/activities?from=YYYY-MM-DD&to=YYYY-MM-DD&limit=50&offset=0&q=关键词
//                                      -> {total, limit, offset, activities: [...]}
//   GET /api/activity/:id                -> 单条活动（含 detail_text）
//   GET /health                          -> ok

const LIST_FIELDS = "id, title, tags, depart_label, date_start, date_end, days, leader, cost_type, signup_count, detail_url, first_seen, last_seen";

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Access-Control-Allow-Origin": "*",
      "Cache-Control": "public, max-age=300",
    },
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (request.method === "OPTIONS") {
      return new Response(null, {
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type",
        },
      });
    }

    const db = env.BULU_DB;
    if (!db) return json({ error: "D1 binding missing" }, 500);

    try {
      if (path === "/health") return json({ ok: true });

      if (path === "/api/meta") {
        const c = await db.prepare("SELECT COUNT(*) AS n FROM activities").first();
        const u = await db
          .prepare("SELECT COUNT(*) AS n FROM activities WHERE date_start >= date('now')")
          .first();
        const g = await db
          .prepare("SELECT MAX(last_seen) AS m FROM activities")
          .first();
        return json({
          count: c.n,
          upcoming_count: u.n,
          generated_at: g.m,
        });
      }

      if (path === "/api/activities") {
        const from = url.searchParams.get("from") || "0000-00-00";
        const to = url.searchParams.get("to") || "9999-99-99";
        const q = (url.searchParams.get("q") || "").trim();
        const limit = Math.min(parseInt(url.searchParams.get("limit") || "50", 10) || 50, 500);
        const offset = Math.max(parseInt(url.searchParams.get("offset") || "0", 10) || 0, 0);

        let where = "date_start >= ? AND date_start <= ?";
        const params = [from, to];
        if (q) {
          where += " AND (title LIKE ? OR leader LIKE ? OR tags LIKE ?)";
          const like = `%${q}%`;
          params.push(like, like, like);
        }
        const total = await db
          .prepare(`SELECT COUNT(*) AS n FROM activities WHERE ${where}`)
          .bind(...params)
          .first();
        const rows = await db
          .prepare(
            `SELECT ${LIST_FIELDS} FROM activities WHERE ${where} ` +
              `ORDER BY date_start, id LIMIT ? OFFSET ?`
          )
          .bind(...params, limit, offset)
          .all();
        return json({
          total: total.n,
          limit,
          offset,
          activities: rows.results || [],
        });
      }

      const m = path.match(/^\/api\/activity\/(\d+)$/);
      if (m) {
        const row = await db
          .prepare(`SELECT ${LIST_FIELDS}, detail_text FROM activities WHERE id = ?`)
          .bind(parseInt(m[1], 10))
          .first();
        if (!row) return json({ error: "not found" }, 404);
        return json(row);
      }

      return json({ error: "not found" }, 404);
    } catch (e) {
      return json({ error: String((e && e.message) || e) }, 500);
    }
  },
};
