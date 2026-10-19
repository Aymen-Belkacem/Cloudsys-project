### 1\. **PaaS / CaaS (Platform &amp; Container as a Service)**

* **AWS App Runner** : Service de conteneurs managé qui héberge l'application web **Streamlit**. Il maintient l'application active en continu pour fournir l'interface utilisateur (Heatmap et filtres) sans nécessiter la gestion directe de machines virtuelles (VM).

### 2\. **Base de données (DBaaS - Database as a Service)**

* **Amazon DocumentDB** : Base de données NoSQL orientée documents (compatible MongoDB). Elle stocke :
  * La collection `trades_matrix` (données de transactions et d'anomalies issues de UN Comtrade).
  * La collection `reports_metadata` (historique et métadonnées des rapports PDF générés).

### 3\. **FaaS (Function as a Service / Serverless Compute)**

Composants de calcul ponctuel s'exécutant uniquement à la demande (*event-driven*) :

* **Lambda\_ETL** : Traite et nettoie les fichiers de données bruts lors de leur dépôt.
* **Lambda\_Calc** : Exécute le calcul des prix unitaires et applique les règles de détection d'anomalies (FOB &gt; CIF ou Gap &gt; 35%).
* **Lambda\_AI (IA Orchestrator)** : Déclenché lors du clic sur une anomalie pour rassembler le contexte et piloter l'interaction avec l'IA.
* **Lambda\_PDF (PDF Generator)** : Convertit l'explication du LLM en document PDF et sauvegarde le fichier.

### 4\. **Services Managés &amp; SaaS (GenAI, Stockage, Sécurité &amp; Supervision)**

* **Amazon Bedrock (GenAI / LLM as a Service)** : Service managé d'IA générative fournissant les modèles de langage (ex. Claude / Nova) pour rédiger l'explication contextuelle des fraudes.
* **Amazon S3 (Storage as a Service)** : Stockage d'objets hautement disponible. Contient le bucket `raw-comtrade-data` (données brutes) et le bucket `reports-pdf` (fichiers PDF finals).
* **AWS Cognito &amp; AWS IAM (Security &amp; Auth as a Service)** : **Cognito** gère l'authentification des analystes, tandis qu'**IAM** définit les rôles et permissions d'accès sécurisés entre les services AWS.
* **Amazon CloudWatch (Monitoring as a Service)** : Centralise la collecte des logs d'exécution et la surveillance des performances.