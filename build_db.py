import pathlib

import duckdb


con = duckdb.connect("olist.duckdb")

for file in sorted(pathlib.Path("./data").glob("*.csv")):
    name = file.stem.replace("olist_", "").replace("_dataset", "")
    con.execute(
        f'CREATE OR REPLACE TABLE "{name}" AS SELECT * FROM read_csv_auto(?)',
        [str(file)],
    )
    count = con.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
    print(f"{name}: {count} rows")

con.close()
