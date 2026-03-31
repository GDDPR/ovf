To set up indexes in opensearch manually

1. run src/scrape/catalogbuild.py (creates xml file)
2. run src/scrape/parse_catalog.py (creates chunks and saves as json)
3. run src/ingest/create_index.py
4. run src/ingest/embed_sections.py
5. run src/ingest/ingest_sections.py

To use the model:

1. Create the Docker volume:
docker volume create opensearch_data

2. Extract the backup:
mkdir restore_tmp
tar xzf opensearch_data_backup.tar.gz -C restore_tmp

3. Copy the extracted data into the Docker volume:
docker run --rm -v opensearch_data:/target -v "$(pwd)/restore_tmp/opensearch_data:/source" alpine sh -c 'cp -a /source/. /target/'

4. Start the containers:
docker compose up -d