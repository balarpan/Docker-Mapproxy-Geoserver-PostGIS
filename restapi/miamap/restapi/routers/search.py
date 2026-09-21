from fastapi import APIRouter, Query
from typing import Annotated
from stngs import settings as stngs
from db import PgDbHandler 

db = PgDbHandler(stngs)
router = APIRouter(prefix="/v1", tags=["search"])

@router.get("/find_place",
            summary="Find a country and optionally city in that country",
            response_description="List of found names and XY of bounding box for countries")
async def find_place(
    lang: Annotated[
      str,
      Query(
        min_length=2,
        pattern="^[a-zA-Z0-9-]+$",
        description="ISO-639-1 code of language(in lowercase where applicable). For languages with multiple scripts or regional variations, extended codes are used, such as 'zh-Hans' for Simplified Chinese or 'zh-Hant' for Traditional Chinese.",
        examples=["ru", "en", "de", "zh-Hans"]
    )],
    country: Annotated[
      str | None,
      Query(min_length=2, description="partial name of the Country to search for")
    ] = None,
    city: Annotated[
      str | None,
      Query(min_length=2, description="the initial letters of the city name for search")
    ] = None,
    country_area_id: Annotated[
      int | None,
      Query(description="country area_id for searching city")
    ] = None,
    limit: Annotated[
        int,
        Query( ge=1, le=100, description="maximum number of returned values")
    ] = 20
):
    """
    Поиск страны по ее первым буквам и, опционально, населенного пункта в стране.
    Если задано только название страны, то будут найдены все страны, начинаюшиеся с указанного набора символов.
    Если задано country_area_id, то ищется населенный пункт по его первым буквам в названии.

    Язык, на котором необходимо выполнять поиск названий задается отдельным параметром согласно стандарту [ISO-639-1](https://ru.wikipedia.org/wiki/ISO_639-1)
    """
    if country_area_id is None:
        ret = db.exec_query(
            f"""
            SELECT area_id, name, admin_level, ST_XMin(ext) AS xmin, ST_YMin(ext) AS ymin, ST_XMax(ext) AS xmax, ST_YMax(ext) AS ymax
            FROM (
              SELECT area_id, (tags->>'name:{lang}') as name, admin_level, ST_Extent(geom) as ext
              FROM {stngs.db.db_schema}.adm_border
              WHERE admin_level<3 AND (tags->>'name:{lang}') ilike :ctry
              GROUP BY (tags->>'name:{lang}'), area_id, admin_level
              LIMIT {limit}
            ) as sub;
            """,
            {"ctry": f"{country}%"})
        return {"input_country": country, "input_lang": lang, "found": ret}
    ret = db.exec_query(f"""
SELECT name, place, x, y
FROM(
 SELECT 1 as qry_order, name, place, ST_X(pnt) as x, ST_Y(pnt) as y
 FROM (
  SELECT (p.tags->>'name:{lang}') as name, 'capital' as place, p.geom as pnt
  FROM {stngs.db.db_schema}.capital_pnt p, {stngs.db.db_schema}.adm_border poly
  WHERE poly.area_id = :ctry_id
    AND p.geom && poly.geom
    AND ST_Contains(poly.geom, p.geom)
    AND (p.tags->>'name:{lang}') ilike :city
  GROUP BY (p.tags->>'name:{lang}'), p.capital, p.geom
  LIMIT {limit}
) as sub1

 UNION

 SELECT 1 as qry_order, name, place, ST_X(pnt) as x, ST_Y(pnt) as y
 FROM (
  SELECT (p.tags->>'name:{lang}') as name, p.place as place, p.population as population, p.geom as pnt
  FROM {stngs.db.db_schema}.city_pnt p, {stngs.db.db_schema}.adm_border poly
  WHERE poly.area_id = :ctry_id
    AND p.geom && poly.geom
    AND ST_Contains(poly.geom, p.geom)
    AND (p.tags->>'name:{lang}') ilike :city
  GROUP BY (p.tags->>'name:{lang}'), p.population, p.place, p.geom
  ORDER BY
    CASE place
      WHEN 'city' THEN 1
      WHEN 'town' THEN 2
      WHEN 'village' THEN 3
      WHEN 'hamlet' THEN 4
    END, name ASC, population DESC
  LIMIT {limit}
 ) as sub2
) as combined
ORDER BY qry_order ASC,
    CASE place
      WHEN 'capital' THEN 0
      WHEN 'city' THEN 1
      WHEN 'town' THEN 2
      WHEN 'village' THEN 3
      WHEN 'hamlet' THEN 4
    END,
  name ASC
;
    """, {"city": f"{city}%", "ctry_id": country_area_id})
    return {"input_country_id": country_area_id, "input_city": city, "input_lang": lang, "found": ret}
