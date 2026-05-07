-- SPDX-FileCopyrightText: OpenAI
--
-- SPDX-License-Identifier: AGPL-3.0-or-later

CREATE SCHEMA IF NOT EXISTS entsoe;

CREATE OR REPLACE FUNCTION entsoe.normalize_area_name(label text)
RETURNS text
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $$
SELECT CASE
    WHEN label IS NULL OR btrim(label) = '' THEN NULL
    WHEN label ~ '\([A-Z]{2}\)$' THEN regexp_replace(label, '^.*\(([A-Z]{2})\)$', '\1')
    ELSE upper(
        trim(both '_' FROM regexp_replace(
            regexp_replace(label, '[^A-Za-z0-9]+', '_', 'g'),
            '_+',
            '_',
            'g'
        ))
    )
END
$$;

CREATE OR REPLACE FUNCTION entsoe.normalize_country_name(label text)
RETURNS text
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $$
SELECT CASE label
    WHEN 'Albania' THEN 'AL'
    WHEN 'Austria' THEN 'AT'
    WHEN 'Belgium' THEN 'BE'
    WHEN 'Bosnia and Herzegovina' THEN 'BA'
    WHEN 'Bulgaria' THEN 'BG'
    WHEN 'Croatia' THEN 'HR'
    WHEN 'Cyprus' THEN 'CY'
    WHEN 'Czechia' THEN 'CZ'
    WHEN 'Denmark' THEN 'DK'
    WHEN 'Estonia' THEN 'EE'
    WHEN 'Finland' THEN 'FI'
    WHEN 'France' THEN 'FR'
    WHEN 'Georgia' THEN 'GE'
    WHEN 'Germany' THEN 'DE'
    WHEN 'Greece' THEN 'GR'
    WHEN 'Hungary' THEN 'HU'
    WHEN 'Ireland' THEN 'IE'
    WHEN 'Italy' THEN 'IT'
    WHEN 'Kosovo' THEN 'XK'
    WHEN 'Latvia' THEN 'LV'
    WHEN 'Lithuania' THEN 'LT'
    WHEN 'Luxembourg' THEN 'LU'
    WHEN 'Moldova' THEN 'MD'
    WHEN 'Montenegro' THEN 'ME'
    WHEN 'Netherlands' THEN 'NL'
    WHEN 'North Macedonia' THEN 'MK'
    WHEN 'Norway' THEN 'NO'
    WHEN 'Poland' THEN 'PL'
    WHEN 'Portugal' THEN 'PT'
    WHEN 'Romania' THEN 'RO'
    WHEN 'Serbia' THEN 'RS'
    WHEN 'Slovakia' THEN 'SK'
    WHEN 'Slovenia' THEN 'SI'
    WHEN 'Spain' THEN 'ES'
    WHEN 'Sweden' THEN 'SE'
    WHEN 'Switzerland' THEN 'CH'
    WHEN 'Turkey' THEN 'TR'
    WHEN 'Ukraine' THEN 'UA'
    WHEN 'United Kingdom' THEN 'GB'
    ELSE entsoe.normalize_area_name(label)
END
$$;
