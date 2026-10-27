---
date: 06.10.2026
---
### présentation du projet 3
- comparaison entre les records de l'export et l'import pour le blé et cela permet de checker les anomalies et les fraudes
- c'est quoi une anomalie ?
	- france déclare 1000t, mais égypte pas...
	- c'est quand l'export et l'import ne match pas
- architecture
	- database
		- 3 sources de données
			- national authority : achat des données d'export et import
			- eurostat : statistiques européennes
			- UN Comtrade : informations fournit pas les nations unies (genève)
				- offre des données gratuites mais limitées
				- seul trucs qu'on va utiliser
				- interface qui permet de télécharger les informations
					- export, import, pays, etc.
				- dataset déjà prêt dans Teams
				- forme des données
					- period (années)
					- reporter
					- flow (export ou import)
					- partner
					- HS (code qui permet de reconnaitre le produit, par exemple blé c'est 1001) harmonized system
						- il y a des sous-codes pour le type de blés...
						- les sous-codes sont spécifiques aux pays, mais les 4 chiffres sont communs
					- trade value ($)
					- net weight (kg)
	- computation engine
		- ici on trouve les anomalies
		- 2 cas, 2 fonctions pour trouver les anomaliess
		- concepts
			- unit price = trade value / quantity (USD/kg) c'est ce qui est utilisé pour checker dans les trades
			- FOB (Free On Board) : prix unitaire de la part de l'exportateur, la valeur à l'exportateur, c'est juste le prix de la marchandises
			- **CIF** (Cost Insurance Freight) : **FOB** + Freight (transport, on a pas les données) + **insurance** (assurance sur le transport, qui est négligable)
		- 2 cas d'anomalies
			1. FOB > CIF : pas possible, car CIF ça prend le transport et l'assurance en plus
			2. Gap > 35% : c'est les analystes qui ont définit cette valeur, qui ne pourrait pas dépasser 35%
			3. Gap = (CIF - FOB) / FOB
			- c'est cela seulement qu'on va implémenter pour cette partie
	- user interface 
		- permet de voir les choses..
		- informations à avoir sur l'interface :
			- on fixe l'exportateur, le produit et la fréquence, mensuelles, annuelles, etc.
			- bouton Show
			- heatmap avec :
				- axe x : fréquence (année)
				- axe y : pays partenaire, à qui la france a envoyé par exemple
			- si y'a une anomalie, on définit comme anomalie, ce qui fait un heapmap
			- on peut choisir les top 10 pays seulement
			- on peut mettre un hover sur les cellules avec les informations sur l'anomalie ou non
	- ai layer
		- llm qui peut collecter le contexte pour un transaction pour ensuite donner aux analystes
		- on essaie d'expliquer les anomalies
		- raisons
			- rerouting via third countries
				- par exemple en 2022 l'Ukraine export du blé et corn pour l'égypte, mais ils passent par la turquie, après, mais l'égytpe disent qu'il reçoivent de l'ukraine
			- tariffs and sanctions
			- wad and conflicts
			- data-entry errors
		- en utilisant les LLM 
			- red cell : gather contexte --> LLM writes explanation --> PDF report --> stored instantly
- on sera noté sur l'architecture, le use case c'est juste pour donner 

![[IMG_2369.jpeg]]

prochaines étapes :
- semaine prochaine (13.10.2026) : architecture globale de la plateforme
	- composants sur quel archi ?
	- quels services cloud ?
	- DNEXT travaille avec AWS
	- la forme de la présentation libre
