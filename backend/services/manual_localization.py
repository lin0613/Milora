"""Admin-authored plain-text translations, independent of replaceable source rows."""
import json
import sqlite3

SCHEMA_SQL = """create table if not exists manual_content_localizations (
 resource_type text not null, game_id text not null, resource_id text not null,
 language text not null, fields_json text not null, updated_by text not null,
 updated_at integer not null,
 primary key(resource_type,game_id,resource_id,language)
)"""
LANGUAGES = ('en', 'ja', 'zh-Hans')
FIELD_LIMITS = {'achievement': {'name': 300, 'condition': 5000},
                'category': {'name': 200}, 'redeem_game': {'name': 120}}


def overrides(db, kind, game_id):
    try:
        rows=db.execute('select resource_id,language,fields_json from manual_content_localizations where resource_type=? and game_id=?',(kind,game_id)).fetchall()
    except sqlite3.OperationalError as exc:
        if 'no such table: manual_content_localizations' in str(exc): return {}
        raise
    result={}
    for row in rows:
        result.setdefault(str(row['resource_id']),{})[str(row['language'])]=json.loads(row['fields_json'])
    return result


def merge(source, manual):
    result={language:dict(fields) for language,fields in (source or {}).items()}
    for language,fields in (manual or {}).items(): result.setdefault(language,{}).update(fields)
    return result


def save(db, kind, game_id, resource_id, language, fields, actor, stamp):
    if kind not in FIELD_LIMITS or language not in LANGUAGES:
        raise ValueError('不支援的資源類型或語言。繁體請使用原本儲存功能。')
    if not isinstance(fields,dict) or not fields or set(fields)-set(FIELD_LIMITS[kind]):
        raise ValueError('翻譯欄位不正確。')
    cleaned={}
    for field,value in fields.items():
        if not isinstance(value,str) or len(value)>FIELD_LIMITS[kind][field] or '\x00' in value:
            raise ValueError('翻譯內容格式不正確或超過字數限制。')
        cleaned[field]=value.strip()
    before=overrides(db,kind,game_id).get(resource_id,{}).get(language,{})
    after=dict(before)
    for field,value in cleaned.items():
        if value: after[field]=value
        else: after.pop(field,None)
    if after:
        db.execute('''insert into manual_content_localizations values(?,?,?,?,?,?,?)
          on conflict(resource_type,game_id,resource_id,language) do update set
          fields_json=excluded.fields_json,updated_by=excluded.updated_by,updated_at=excluded.updated_at''',
          (kind,game_id,resource_id,language,json.dumps(after,ensure_ascii=False),actor,stamp))
    else:
        db.execute('delete from manual_content_localizations where resource_type=? and game_id=? and resource_id=? and language=?',(kind,game_id,resource_id,language))
    return before,after
