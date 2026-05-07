# SPDX-FileCopyrightText: Johannes Schuhmacher, Andre Meyer
#
# SPDX-License-Identifier: AGPL-3.0-or-later

# from sqlalchemy.schema import MetaData
from crawler.common.base_crawler import BaseCrawler
import eurostat
import logging
# from gzip import decompress
# import requests
from sqlalchemy import text, Table, MetaData, Column, Integer, String, Float, UniqueConstraint
from sqlalchemy.dialects.postgresql import insert
import sys

class EurostatCrawler(BaseCrawler):
    def __init__(self, crawler_name, config):
        super().__init__(crawler_name, config)
        self.schema_name = self.get('schema_name')
        self.table_name = 'eurostat'  # ?TODO: name eurostat_{dataset_id}?
        self.unique_constraint_name = 'year_geo_siec_tec'

        self._init_table_object()

    def _init_table_object(self):
        self.metadata = MetaData(schema=self.schema_name)
        self.table = Table(
            self.table_name,
            self.metadata,
            Column('year', Integer),
            Column('geo\\TIME_PERIOD', String),
            Column('siec', String),
            Column('plant_tec', String),
            Column('freq', String),
            Column('unit', String),
            Column('capacity', Float),
            UniqueConstraint('year', 'geo\\TIME_PERIOD', 'siec', 'plant_tec', name=self.unique_constraint_name),
        )

    def _create_table(self):
        self.metadata.create_all(self.engine, tables=[self.table])
        self.logger.info(f'Table {self.table_name} created succsessfully')

        with self.engine.begin() as conn:
            query_create_hypertable = "SELECT public.create_hypertable(:table_name, 'year', if_not_exists => TRUE, migrate_data => TRUE);"
            conn.execute(text(query_create_hypertable), {'table_name': f'{self.schema_name}.{self.table_name}'})
            self.logger.info('Hypertable created')


    # 1990 - 2023 is the whole dataset
    def _download_data_df(self):
        start_year = self.get('start_year')
        end_year = self.get('end_year')
        df = eurostat.get_data_df(
            self.get('dataset_id'),
            filter_pars={'startPeriod': start_year, 'endPeriod': end_year}
        )

        if df is None:
            self.logger.error(f'No data downloaded for years {start_year} - {end_year}')
            return

        available_year_columns = [
            str(year) for year in range(start_year, end_year + 1) if str(year) in df.columns
        ]

        if not available_year_columns:
            self.logger.error(
                f'No requested year columns are available for dataset {self.get("dataset_id")} '
                f'in range {start_year} - {end_year}'
            )
            return None

        # reshape the dataframe so that year can be used as a column inorder for the hypertable to work
        df = df.melt(
            id_vars=['freq', 'siec', 'plant_tec', 'unit', 'geo\\TIME_PERIOD'],
            value_vars=available_year_columns,  # in the dataframe the years are strings at first
            var_name='year',
            value_name='capacity'
        )
        df['year'] = df['year'].astype(int)  # convert year string to int
        df = df.dropna(subset=['capacity'])

        return df

    def _write_to_db(self, df):
        stmt = insert(self.table)
        stmt = stmt.on_conflict_do_update(
            constraint=self.unique_constraint_name,
            set_=stmt.excluded,
        )
        stmt = stmt.values(df.to_dict(orient='records'))

        with self.engine.begin() as conn:
            conn.execute(stmt)
        self.logger.info('Data written to Database')

    def run(self):
        self.set_metadata({
            'schema_name': self.get('schema_name'),
            'data_date': '2024-06-12',
            'data_source': 'https://www.eurostat.europa.eu/',
            'license': '',
            'description': '',
            'contact': '',
            'temporal_start': '1990-01-01 00:00:00',
            'temporal_end': '2023-12-31 23:59:59',
            'concave_hull_geometry': None,
        })
        self._create_table()
        df = self._download_data_df()

        if df is None:
            self.logger.error('No data to write to Database')
            return

        self._write_to_db(df)

def main(schema_name):
    ec = EurostatCrawler(
        'eurostat_crawler',
        {
            'database_uri': 'postgresql://opendata:opendata@localhost:6432/opendata?options=--search_path=',
            'schema_name': 'eurostat',
            'dataset_id': 'nrg_inf_epcrw',
            'start_year': 2022,
            'end_year': 2023
        }
    )
    ec.run()

if __name__ == '__main__':
    logging.basicConfig(
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('eurostat.log')
        ],
        encoding='utf-8',
        level=logging.INFO
    )
    main('eurostat')
