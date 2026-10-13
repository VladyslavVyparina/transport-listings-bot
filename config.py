BOT_TOKEN = "YOUR_TRANSPORT_BOT_TOKEN_HERE"

# Групи, звідки ловимо вільний транспорт.
# Порожній список = усі групи, куди додано бота (крім REPOST і MANAGER).
SOURCE_GROUP_IDS = []

# Група, куди репостимо транспорт БЕЗ контактів, з посиланням на logistics-бота
REPOST_GROUP_ID = -1004405977967

# Внутрішній чат менеджерів (повні дані з контактами)
MANAGER_CHAT_ID = -1004405977967

# ID каналу для пуш-повідомлень
CHANNEL_ID = -1002120477749

# Google Sheets settings (та ж таблиця що і в logistics боті)
GOOGLE_SHEET_ID = "1Z_H5i_Fore1IuVz2lR49NDe7A-dVpiORtwtyfKvN1J8"
GOOGLE_SHEET_RANGE = "B:H"

# Username логістичного бота без @ — саме туди ведуть кнопки з репостів
LOGISTICS_BOT_USERNAME = "inter_logistics_bot"

# Спільна база карток транспорту для зв'язки з inter_logistics_bot
LISTINGS_PATH = "/Users/macbookpro/Desktop/transport_bot/listings.json"
