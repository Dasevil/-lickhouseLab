import pymongo
from datetime import datetime

client = pymongo.MongoClient("mongodb://root:rootpass@localhost:27017/")
db = client.ecom_catalog
categories_collection = db.categories
products_collection = db.products

# Задание 3.1: Аналитика по категориям

# Агрегация 1: Топ-10 категорий по количеству товаров с детальной статистикой
print("\n=== АГРЕГАЦИЯ 1: ТОП-10 КАТЕГОРИЙ ПО КОЛИЧЕСТВУ ТОВАРОВ ===")
pipeline1 = [
    {
        "$group": {
            "_id": "$category.id",
            "count": { "$sum": 1 },
            "name": { "$first": "$category.name" },
            "full_path": { "$first": "$category.full_path" }
        }
    },
    {
        "$sort": { "count": -1 }
    },
    {
        "$limit": 10
    }
]
result1 = list(products_collection.aggregate(pipeline1))
print(f"Найдено документов: {len(result1)}")
print("Результаты:")
print("| category_id | название категории | полный путь | количество товаров |")
print("|---|---|---|---|")
for doc in result1:
    print(f"| {doc['_id']} | {doc['name']} | {doc['full_path']} | {doc['count']} |")

# Время выполнения агрегации
explain_result = db.command({
    "aggregate": "products",
    "pipeline": pipeline1,
    "explain": True
})
# Печать полного результата explain для диагностики
print(f"Полный результат explain: {explain_result}")

# Интерпретация
if result1:
    print(f"Самая большая категория по количеству товаров: {result1[0]['name']} с {result1[0]['count']} товарами")

# Агрегация 2: Иерархическая статистика по уровням
print("\n=== АГРЕГАЦИЯ 2: ИЕРАРХИЧЕСКАЯ СТАТИСТИКА ПО УРОВНЯМ ===")
pipeline2 = [
    {
        "$unwind": "$category.breadcrumbs"
    },
    {
        "$group": {
            "_id": {
                "level": "$category.breadcrumbs.level",
                "name": "$category.breadcrumbs.name"
            },
            "count": { "$sum": 1 }
        }
    },
    {
        "$sort": { "_id.level": 1, "count": -1 }
    },
    {
        "$limit": 30
    }
]
result2 = list(products_collection.aggregate(pipeline2))
print(f"Найдено документов: {len(result2)}")
print("Результаты:")
print("| уровень | название категории | количество товаров |")
print("|---|---|---|")
for doc in result2:
    print(f"| {doc['_id']['level']} | {doc['_id']['name']} | {doc['count']} |")

# Интерпретация
if result2:
    print("\nИнтерпретация:")
    print(f"- Больше всего товаров на уровне {result2[0]['_id']['level']} (категория {result2[0]['_id']['name']})")
    
    # Топ-3 на 1-м уровне
    top_level1 = [doc for doc in result2 if doc['_id']['level'] == 1][:3]
    print("- Топ-3 на 1-м уровне:")
    for i, doc in enumerate(top_level1, 1):
        print(f"  {i}. {doc['_id']['name']}: {doc['count']} товаров")
    
    # Топ-3 на 2-м уровне
    top_level2 = [doc for doc in result2 if doc['_id']['level'] == 2][:3]
    print("- Топ-3 на 2-м уровне:")
    for i, doc in enumerate(top_level2, 1):
        print(f"  {i}. {doc['_id']['name']}: {doc['count']} товаров")
    
    # Топ-3 на 3-м уровне
    top_level3 = [doc for doc in result2 if doc['_id']['level'] == 3][:3]
    print("- Топ-3 на 3-м уровне:")
    for i, doc in enumerate(top_level3, 1):
        print(f"  {i}. {doc['_id']['name']}: {doc['count']} товаров")

# Задание 3.3: Анализ структуры категорий

# Агрегация А: Распределение категорий по уровням и партнерам
print("\n=== АГРЕГАЦИЯ А: РАСПРЕДЕЛЕНИЕ КАТЕГОРИЙ ПО УРОВНЯМ И ПАРТНЕРАМ ===")
pipeline_a = [
    {
        "$group": {
            "_id": {
                "partner": "$partner",
                "level": "$level"
            },
            "category_count": { "$sum": 1 },
            "total_products": { "$sum": "$metadata.total_products" }
        }
    },
    {
        "$sort": { "_id.partner": 1, "_id.level": 1 }
    }
]
result_a = list(categories_collection.aggregate(pipeline_a))
print(f"Найдено документов: {len(result_a)}")
print("Результаты:")
print("| партнер | уровень | количество категорий | сумма товаров |")
print("|---|---|---|---|")
for doc in result_a:
    print(f"| {doc['_id']['partner']} | {doc['_id']['level']} | {doc['category_count']} | {doc['total_products']} |")

# Подсчет средней глубины
if result_a:
    total_levels = sum(doc['_id']['level'] * doc['category_count'] for doc in result_a)
    total_categories = sum(doc['category_count'] for doc in result_a)
    avg_depth = total_levels / total_categories
    print(f"Средняя глубина категорий: {avg_depth:.2f} уровня")

# Агрегация Б: Категории-"листья" (конечные категории без подкатегорий)
print("\n=== АГРЕГАЦИЯ Б: КАТЕГОРИИ-ЛИСТЬЯ ===")
pipeline_b = [
    {
        "$lookup": {
            "from": "categories",
            "localField": "path",
            "foreignField": "parent_path",
            "as": "children"
        }
    },
    {
        "$match": {
            "children": { "$size": 0 }
        }
    },
    {
        "$sort": { "metadata.total_products": -1 }
    },
    {
        "$limit": 10
    }
]
result_b = list(categories_collection.aggregate(pipeline_b))
print(f"Найдено документов: {len(result_b)}")
print("Топ-10 категорий-листьев:")
print("| название категории | полный путь | количество товаров |")
print("|---|---|---|")
for doc in result_b:
    print(f"| {doc['name']} | {doc['path']} | {doc['metadata']['total_products']} |")

# Вывод
print("\nВывод:")
if result_b:
    print(f"Существуют категории-листья с большим количеством товаров. ")
    print(f"Наибольшее количество товаров в категории-листье: {result_b[0]['metadata']['total_products']}")
    if result_b[0]['metadata']['total_products'] > 100:
        print("Такие категории могут быть кандидатами на разбиение на подкатегории для улучшения навигации.")

# Закрываем соединение
client.close()