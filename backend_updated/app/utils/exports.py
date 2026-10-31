import io
import json

import pandas as pd
from fastapi.responses import StreamingResponse


def _serializable(value):
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return value


def prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    for column in result.columns:
        result[column] = result[column].map(_serializable)
    return result.fillna("")


def dataframe_download(df: pd.DataFrame, filename: str, file_format: str):
    df = prepare_dataframe(df)
    if file_format == "csv":
        content = io.StringIO()
        df.to_csv(content, index=False)
        return StreamingResponse(
            iter([content.getvalue().encode("utf-8-sig")]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
        )

    if file_format == "xlsx":
        content = io.BytesIO()
        with pd.ExcelWriter(content, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Results")
        content.seek(0)
        return StreamingResponse(
            content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'},
        )

    raise ValueError("Unsupported export format. Use csv or xlsx.")


def workbook_download(sheets: dict[str, pd.DataFrame], filename: str):
    content = io.BytesIO()
    with pd.ExcelWriter(content, engine="openpyxl") as writer:
        for name, df in sheets.items():
            prepare_dataframe(df).to_excel(writer, index=False, sheet_name=name[:31])
    content.seek(0)
    return StreamingResponse(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'},
    )