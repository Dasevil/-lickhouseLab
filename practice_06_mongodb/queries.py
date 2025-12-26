import pymongo
from datetime import datetime

client = pymongo.MongoClient("mongodb://root:rootpass@localhost:27017/")
db = client.ecom_catalog
categories_collection = db.categories
products_collection = db.products

# Задание 2.1: Навигация по иерархии категорий

# Запрос 1: Найти все категории первого уровня (корневые) для партнера "_ozon"
print("\n=== ЗАПРОС 1: КОРНЕВЫЕ КАТЕГОРИИ ДЛЯ _ozon ===")
query1 = {
    "partner": "_ozon",
    "level": 1
}
result1 = list(categories_collection.find(query1))
print(f"Найдено документов: {len(result1)}")
print("Первые 3 результата:")
for doc in result1[:3]:
    print(f"- {doc['name']}: {doc['metadata']['total_products']} товаров")

# Объяснение запроса 1
try:
    explain1 = categories_collection.find(query1).explain()
    print(f"Используемый индекс: {explain1['queryPlanner']['winningPlan']['inputStages'][0]['indexName'] if 'indexName' in explain1['queryPlanner']['winningPlan']['inputStages'][0] else 'COLLSCAN'}")
except (KeyError, IndexError) as e:
    print(f"Ошибка при анализе индекса: {e}")
    print(f"Полный план: {explain1}")

# Запрос 2: Найти все подкатегории (любого уровня), которые входят в "Строительство и ремонт"
print("\n=== ЗАПРОС 2: ПОДКАТЕГОРИИ \"Строительство и ремонт\" ===")
query2 = {
    "path_array": { "$regex": "^Строительство и ремонт" }
}
result2 = list(categories_collection.find(query2))
print(f"Найдено документов: {len(result2)}")
print("Первые 3 результата:")
for doc in result2[:3]:
    print(f"- {doc['path']}: {doc['metadata']['total_products']} товаров")

# Объяснение запроса 2
try:
    explain2 = categories_collection.find(query2).explain()
    print(f"Используемый индекс: {explain2['queryPlanner']['winningPlan']['inputStages'][0]['indexName'] if 'indexName' in explain2['queryPlanner']['winningPlan']['inputStages'][0] else 'COLLSCAN'}")
except (KeyError, IndexError) as e:
    print(f"Ошибка при анализе индекса: {e}")
    print(f"Полный план: {explain2}")

# Запрос 3: Топ-10 самых "населенных" категорий по количеству товаров
print("\n=== ЗАПРОС 3: ТОП-10 ПО КОЛИЧЕСТВУ ТОВАРОВ ===")
query3 = {}
sort3 = [("metadata.total_products", -1)]
result3 = list(categories_collection.find(query3).sort(sort3).limit(10))
print(f"Найдено документов: {len(result3)}")
print("Первые 3 результата:")
for doc in result3[:3]:
    print(f"- {doc['path']}: {doc['metadata']['total_products']} товаров")

# Объяснение запроса 3
try:
    explain3 = categories_collection.find(query3).sort(sort3).limit(10).explain()
    print(f"Используемый индекс: {explain3['queryPlanner']['winningPlan']['inputStages'][0]['indexName'] if 'indexName' in explain3['queryPlanner']['winningPlan']['inputStages'][0] else 'COLLSCAN'}")
except (KeyError, IndexError) as e:
    print(f"Ошибка при анализе индекса: {e}")
    print(f"Полный план: {explain3}")

# Задание 2.2: Работа с товарами и вложенными документами

# Запрос 1: Найти все товары типа "Степлер строительный", у которых в иерархии категорий (breadcrumbs) есть уровень "Пневмоинструменты"
print("\n=== ЗАПРОС 4: ТОВАРЫ С ТИПОМ \"Степлер строительный\" И КАТЕГОРИЕЙ \"Пневмоинструменты\" ===")
query4 = {
    "type": "Степлер строительный",
    "category.breadcrumbs.name": "Пневмоинструменты"
}
result4 = list(products_collection.find(query4))
print(f"Найдено документов: {len(result4)}")
print("Примеры (первые 2 документа):")
for doc in result4[:2]:
    print(f"- {doc['name']}: {doc['category']['full_path']}")

# Объяснение запроса 4
try:
    explain4 = products_collection.find(query4).explain()
    print(f"Используемый индекс: {explain4['queryPlanner']['winningPlan']['inputStages'][0]['indexName'] if 'indexName' in explain4['queryPlanner']['winningPlan']['inputStages'][0] else 'COLLSCAN'}")
except (KeyError, IndexError) as e:
    print(f"Ошибка при анализе индекса: {e}")
    print(f"Полный план: {explain4}")

# Запрос 2: Найти товары, которые находятся на 4-м уровне иерархии категорий
print("\n=== ЗАПРОС 5: ТОВАРЫ НА 4-М УРОВНЕ ИЕРАРХИИ ===")
query5 = {
    "category.breadcrumbs": { "$size": 4 }
}
result5 = list(products_collection.find(query5))
print(f"Найдено документов: {len(result5)}")
print("Примеры (первые 2 документа):")
for doc in result5[:2]:
    print(f"- {doc['name']}: {doc['category']['full_path']}")

# Объяснение запроса 5
try:
    explain5 = products_collection.find(query5).explain()
    print(f"Используемый индекс: {explain5['queryPlanner']['winningPlan']['inputStages'][0]['indexName'] if 'indexName' in explain5['queryPlanner']['winningPlan']['inputStages'][0] else 'COLLSCAN'}")
except (KeyError, IndexError) as e:
    print(f"Ошибка при анализе индекса: {e}")
    print(f"Полный план: {explain5}")

# Запрос 3: Найти количество товаров в каждой категории 1-го уровня
print("\n=== ЗАПРОС 6: РАСПРЕДЕЛЕНИЕ ТОВАРОВ ПО КАТЕГОРИЯМ 1-ГО УРОВНЯ ===")
pipeline6 = [
    {
        "$group": {
            "_id": {
                "$arrayElemAt": ["$category.breadcrumbs.name", 0]
            },
            "count": { "$sum": 1 }
        }
    },
    {
        "$sort": { "count": -1 }
    }
]
result6 = list(products_collection.aggregate(pipeline6))
print(f"Найдено групп: {len(result6)}")
print("Результаты (топ-5):")
for doc in result6[:5]:
    print(f"- {doc['_id']}: {doc['count']} товаров")

# Закрываем соединение
client.close()