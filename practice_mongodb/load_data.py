import pandas as pd
import pyarrow.parquet as pq
import pymongo
from datetime import datetime
import json

# Подключение к MongoDB
client = pymongo.MongoClient("mongodb://root:rootpass@localhost:27017/")
db = client.ecom_catalog
categories_collection = db.categories
products_collection = db.products

# Чтение Parquet файла
file_path = "C:/Users/User/PycharmProjects/ClickhouseLab/data/ozon_inference_2025_10_17_offers_2025_10_17.pq"

df = pd.read_parquet(file_path)

# Добавление префикса к Partner_Name

df['Partner_Name'] = '_' + df['Partner_Name']

# Преобразование NaN значений в None

df = df.where(pd.notnull(df), None)

print(f"Загружено {len(df)} строк данных")
print(f"Уникальных категорий: {df[['Partner_Name', 'Category_ID']].drop_duplicates().shape[0]}")

# Задание 1.1: Анализ данных
print("\n=== АНАЛИЗ ИСХОДНЫХ ДАННЫХ ===")

# 1. Количество уникальных категорий
unique_categories = df[['Partner_Name', 'Category_ID']].drop_duplicates()
print(f"1. Уникальных категорий: {len(unique_categories)}")

# 2. Максимальная глубина вложенности категорий
# Создаем временный DataFrame с путями категорий
paths_df = df[['Partner_Name', 'Category_ID', 'Category_FullPathName']].drop_duplicates()
# Разделяем путь и считаем количество уровней
paths_df['level'] = paths_df['Category_FullPathName'].str.split('\\\\').str.len()
max_depth = paths_df['level'].max()
print(f"2. Максимальная глубина вложенности категорий: {max_depth}")

# 3. Категории с наибольшим количеством товаров
category_product_count = df.groupby(['Partner_Name', 'Category_ID', 'Category_FullPathName']).size().reset_index(name='product_count')
top_categories = category_product_count.sort_values('product_count', ascending=False).head(5)
print(f"3. Топ-5 категорий по количеству товаров:")
for _, row in top_categories.iterrows():
    print(f"   {row['Category_FullPathName']}: {row['product_count']} товаров")

# 4. Проверка на уникальность Offer_ID у разных партнеров
offer_partner_count = df.groupby('Offer_ID')['Partner_Name'].nunique()
duplicate_offers = offer_partner_count[offer_partner_count > 1]
print(f"4. Количество товаров с одинаковыми Offer_ID у разных партнеров: {len(duplicate_offers)}")

# 5. Количество уникальных типов товаров
unique_offer_types = df['Offer_Type'].nunique()
print(f"5. Уникальных типов товаров (Offer_Type): {unique_offer_types}")

# Аналитическая справка
print("\n=== АНАЛИТИЧЕСКАЯ СПРАВКА ===")
print(f"Структура данных представляет собой плоскую таблицу с информацией о товарах интернет-магазина.")
print(f"Каждая строка соответствует одному товару и содержит информацию о партнере, категории, идентификаторе товара и его типе.")
print(f"Категории представлены в виде иерархического пути с разделителем '\\\\', что позволяет определить уровень вложенности.")
print(f"В данных присутствуют {len(unique_categories)} уникальных категорий с максимальной глубиной вложенности {max_depth} уровней.")
print(f"Наиболее насыщенные категории содержат сотни товаров, что указывает на разнообразие ассортимента.")
print(f"Обнаружено {len(duplicate_offers)} товаров с одинаковыми Offer_ID у разных партнеров, что может указывать на дублирование или партнерскую программу.")
print(f"Присутствует {unique_offer_types} уникальных типов товаров, что говорит о широкой продуктовой линейке.")

# Обоснование выбора двух коллекций
print("\n=== ОБОСНОВАНИЕ ВЫБОРА СХЕМЫ ===")
print("Выбор создания двух коллекций (categories и products) вместо одной обусловлен следующими причинами:")
print("1. Нормализация данных: информация о категории (название, путь, уровень) дублируется для каждого товара в категории.")
print("   Выделение категорий в отдельную коллекцию позволяет избежать избыточного хранения одинаковой информации.")
print("2. Независимость обновлений: метаданные категории (например, общее количество товаров) могут обновляться независимо от товаров.")
print("   Это позволяет эффективно поддерживать актуальность информации о категориях.")
print("3. Гибкость запросов: отдельная коллекция категорий позволяет выполнять иерархические запросы (поиск подкатегорий,")
print("   навигация по уровням) без необходимости сканирования всей коллекции товаров.")
print("4. Эффективность индексации: индексы для коллекции категорий могут быть оптимизированы под иерархические запросы,")
print("   а индексы для коллекции товаров - под поисковые и аналитические запросы.")

# Преимущества денормализации
print("\n=== ПРЕИМУЩЕСТВА ДЕНОРМАЛИЗАЦИИ ===")
print("Денормализация данных в данном кейсе имеет следующие преимущества:")
print("1. Производительность запросов: в коллекции товаров информация о категории дублируется (вложенный документ category),")
print("   что позволяет получать полную информацию о товаре и его категории одним запросом без JOIN операций.")
print("2. Упрощение запросов: клиентское приложение может отображать информацию о категории (название, полный путь)")
print("   без необходимости выполнять дополнительные запросы к коллекции категорий.")
print("3. Снижение нагрузки на базу данных: отсутствие необходимости в соединениях уменьшает нагрузку на сервер,")
print("   особенно при высокой частоте запросов к товарам.")
print("4. Масштабируемость: документо-ориентированная модель с денормализацией лучше масштабируется по горизонтали,")
print("   так как каждый документ содержит всю необходимую информацию для типовых операций.")

# Задание 1.2: Создание коллекции категорий
categories_collection.delete_many({})

print("\n=== СОЗДАНИЕ КОЛЛЕКЦИИ КАТЕГОРИЙ ===")

categories = {}

# Группируем по партнеру и категории для подсчета товаров

category_stats = df.groupby(['Partner_Name', 'Category_ID', 'Category_FullPathName']).size().reset_index(name='total_products')

for _, row in category_stats.iterrows():
    partner = row['Partner_Name']
    category_id = str(row['Category_ID'])
    full_path_name = row['Category_FullPathName']
    
    # Создаем id в формате "partner_categoryid"
    doc_id = f"{partner}_{category_id}"
    
    # Разделяем путь по разделителю "\\\\"
    path_parts = full_path_name.split('\\\\')
    
    # Определяем уровень (количество элементов в пути)
    level = len(path_parts)
    
    # Название категории - последний элемент пути
    name = path_parts[-1]
    
    # Формируем путь с разделителем "/"
    path = "/".join(path_parts)
    
    # Массив элементов пути для иерархических запросов
    path_array = path_parts
    
    # Путь к родительской категории (все элементы пути кроме последнего)
    parent_path = None
    if level > 1:
        parent_path = "/".join(path_parts[:-1])
    
    # Создаем документ категории
    category_doc = {
        "_id": doc_id,
        "partner": partner,
        "category_id": category_id,
        "name": name,
        "path": path,
        "path_array": path_array,
        "level": level,
        "parent_path": parent_path,
        "metadata": {
            "total_products": int(row['total_products']),
            "last_updated": datetime.utcnow()
        }
    }
    
    categories[doc_id] = category_doc

# Вставляем документы в коллекцию
if categories:
    result = categories_collection.insert_many(list(categories.values()))
    print(f"Вставлено {len(result.inserted_ids)} документов в коллекцию categories")
else:
    print("Нет данных для вставки в коллекцию categories")

# Статистика по уровням вложенности
level_stats = categories_collection.aggregate([
    {
        "$group": {
            "_id": "$level",
            "count": { "$sum": 1 }
        }
    },
    {
        "$sort": { "_id": 1 }
    }
])

print("\n=== СТАТИСТИКА ПО УРОВНЯМ ВЛОЖЕННОСТИ КАТЕГОРИЙ ===")
for stat in level_stats:
    print(f"Уровень {stat['_id']}: {stat['count']} категорий")

# Задание 1.3: Создание коллекции товаров
products_collection.delete_many({})

print("\n=== СОЗДАНИЕ КОЛЛЕКЦИИ ТОВАРОВ ===")

products = []

for _, row in df.iterrows():
    partner = row['Partner_Name']
    offer_id = str(row['Offer_ID'])
    
    # Создаем id в формате "partner_offerid"
    doc_id = f"{partner}_{offer_id}"
    
    # Получаем информацию о категории
    category_id = str(row['Category_ID'])
    full_path_name = row['Category_FullPathName']
    
    # Разделяем путь по разделителю "\\\\"
    path_parts = full_path_name.split('\\\\')
    
    # Формируем путь с разделителем "/"
    full_path = "/".join(path_parts)
    
    # Создаем breadcrumbs - массив объектов для навигации
    breadcrumbs = []
    for i, part in enumerate(path_parts):
        breadcrumbs.append({
            "level": i + 1,
            "name": part
        })
    
    # Создаем документ товара
    product_doc = {
        "_id": doc_id,
        "partner": partner,
        "offer_id": offer_id,
        "name": row['Offer_Name'],
        "type": row['Offer_Type'],
        "category": {
            "id": category_id,
            "name": path_parts[-1],
            "full_path": full_path,
            "breadcrumbs": breadcrumbs
        },
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    products.append(product_doc)

# Вставляем документы в коллекцию
if products:
    result = products_collection.insert_many(products)
    print(f"Вставлено {len(result.inserted_ids)} документов в коллекцию products")
else:
    print("Нет данных для вставки в коллекцию products")

# Статистика по партнерам
partner_stats = products_collection.aggregate([
    {
        "$group": {
            "_id": "$partner",
            "count": { "$sum": 1 }
        }
    },
    {
        "$sort": { "count": -1 }
    }
])

print("\n=== РАСПРЕДЕЛЕНИЕ ТОВАРОВ ПО ПАРТНЕРАМ ===")
for stat in partner_stats:
    print(f"{stat['_id']}: {stat['count']} товаров")

# Топ-5 типов товаров
offer_type_stats = products_collection.aggregate([
    {
        "$group": {
            "_id": "$type",
            "count": { "$sum": 1 }
        }
    },
    {
        "$sort": { "count": -1 }
    },
    {
        "$limit": 5
    }
])

print("\n=== ТОП-5 ТИПОВ ТОВАРОВ ===")
for stat in offer_type_stats:
    print(f"{stat['_id']}: {stat['count']} товаров")

# Задание 1.4: Создание индексов

print("\n=== СОЗДАНИЕ ИНДЕКСОВ ===")

# Индексы для коллекции categories

categories_collection.create_index("path", name="path_text_index", default_language="russian")
print("Создан текстовый индекс на поле path для коллекции categories")

categories_collection.create_index("path_array", name="path_array_index")
print("Создан индекс на поле path_array для коллекции categories")

categories_collection.create_index([("partner", pymongo.ASCENDING), ("level", pymongo.ASCENDING)], name="partner_level_index")
print("Создан составной индекс на поля partner и level для коллекции categories")

categories_collection.create_index("metadata.total_products", name="total_products_index")
print("Создан индекс на поле metadata.total_products для коллекции categories")

# Индексы для коллекции products

products_collection.create_index([("partner", pymongo.ASCENDING), ("category.id", pymongo.ASCENDING)], name="partner_category_id_index")
print("Создан составной индекс на поля partner и category.id для коллекции products")

products_collection.create_index("category.breadcrumbs.name", name="breadcrumbs_name_index")
print("Создан индекс на поле category.breadcrumbs.name для коллекции products")

products_collection.create_index([("type", pymongo.ASCENDING), ("partner", pymongo.ASCENDING)], name="type_partner_index")
print("Создан составной индекс на поля type и partner для коллекции products")

products_collection.create_index("offer_id", name="offer_id_index")
print("Создан индекс на поле offer_id для коллекции products")

print("\n=== ЗАВЕРШЕНИЕ ===")
print("Загрузка данных и создание индексов завершены.")
print("Теперь можно переходить к выполнению запросов и агрегаций.")

# Закрываем соединение
client.close()