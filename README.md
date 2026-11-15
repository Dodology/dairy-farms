DAIRY FARMS

A bilingual (English / Arabic) web app for recording livestock milk production. Farmers and researchers can register animals with their pedigree, log weekly milk yields, and automatically compare lactation curves across seasons, parents and breeds.

Live app: https://dairy-farms-ceefhc5ynrmh9ceck2smsz.streamlit.app/


FEATURES

Email and password accounts, with password reset by email.

English and Arabic interface, with right-to-left layout in Arabic.

Farm profile with country, automatic phone code, and role on the farm.

Cows, buffaloes, camels, sheep and goats, with breed, birth date and sex.

Optional pedigree: mother and father IDs, breeds, and known milk yields.

Weekly milk records with calving date and feeding system.

Automatic charts: lactation curve per animal, current versus previous season, comparison with the mother's yield, monthly totals, and breed comparison.


TECH STACK

Python, Streamlit, pandas, Supabase (PostgreSQL), hosted on Streamlit Community Cloud.


RUN LOCALLY

1. Install the requirements:

    pip install -r requirements.txt

2. Create a Supabase project and add its Session pooler connection string to .streamlit/secrets.toml under a [db] section as url = "your connection string".

3. Start the app:

    streamlit run app.py

Tables are created automatically on first run. Never commit secrets.toml to GitHub.


ROADMAP

Automatic pedigree tree, genetic analysis of the collected data, data export, and a quiz module.
