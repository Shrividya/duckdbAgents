import duckdb
import sys
import threading, time

MAX_ROWS = 200
TIMEOUT_S = 15

def list_tables(con)->list[dict]:
    """Every table or view in the current database , as [{"table":name},..]"""
    rows = con.execute("""SELECT table_name
                          FROM information_schema.tables
                          WHERE table_catalog = current_database()
                            AND table_schema = 'main'
                          ORDER BY table_name""").fetchall()
    tables = [r[0] for r in rows]
    return tables

def describe_table(con, table:str) -> list[dict]:
    """Column names and types for one table/view as [{"column":...,"type":...}]."""
    known = { t for t in list_tables(con)}
    if table not in known:
        return [{"error":f"No table name '{table}'.Call list_tables first."}]
    rows = con.execute("""SELECT column_name,data_type 
                            FROM information_schema.columns
                            WHERE table_catalog = current_database()
                                 AND table_schema = 'main'
                                 AND table_name = ?
                            ORDER BY ordinal_position""",[table]).fetchall()
    return [{"column":name, "type": dtype} for name , dtype in rows]


def run_sql(con, sql,max_rows=200, timeout_s=15)-> list[dict]:
    """Run ONE read-only SELECT. Always returns a dict; errors are data."""
    sql = sql.strip().rstrip(";")

    try:
        statements = duckdb.extract_statements(sql)
    except duckdb.Error as e:
        return {"error": str(e)}
    if len(statements) != 1 or statements[0].type != duckdb.StatementType.SELECT:
        return {"error": "Only a single SELECT statement is allowed."}
 
    cur = con.cursor()
    timer = threading.Timer(timeout_s, cur.interrupt)
    started = time.perf_counter()
    timer.start()
    try:
        res = cur.execute(sql)
        columns = [d[0] for d in res.description]
        rows = res.fetchmany(max_rows + 1)
    except duckdb.InterruptException:
        return {"error": f"Query exceeded {timeout_s}s and was cancelled. "
                         "Add filters or aggregate more before retrying."}
    except duckdb.Error as e:
        return {"error": str(e)}
    finally:
        timer.cancel()
 
    truncated = len(rows) > max_rows
    rows = rows[:max_rows]
    return {
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "truncated": truncated,
        "note": (f"Showing first {max_rows} rows; more exist. "
                 "Aggregate or filter instead of paging.") if truncated else None,
        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
    }
    

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "olist.duckdb"
    con = duckdb.connect(db_path,read_only=True)
    print("list_tables:")
    print(list_tables(con))
    print("\n describe_table('orders'):")
    for col in describe_table(con,"orders"):
        print(" ", col)
    print("\ndescribe_table with a hostile name:")
    print(describe_table(con,"orders; DROP VIEW orders"))
    print("\n run_sql tests:")
    tests =[
        ("normal query", lambda:run_sql(con, "SELECT count(*) FROM orders")),
        ("not a SELECT", lambda:run_sql(con, "DROP VIEW orders")),
        ("typo in column", lambda: run_sql(con, "SELECT custmer_id FROM orders")),
        ("row cap", lambda: run_sql(con,"SELECT * from geolocation", max_rows=10)),
        ("timeout", lambda: run_sql(con, "SELECT count(*) from range(10000000000) a, range(10000000000) b", timeout_s=1)),
    ]

    for label, fn in tests:
        r=fn()
        if "error" in r:
            print(f"{label}: ERROR - > {r['error'][:120]}")
        else:
            print(f"{label}: {r['row_count']} row(s), truncated= {r['truncated']}, {r['duration_ms']} ms")