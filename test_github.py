import requests

# hacer la petición get a Github API
url = "https://api.github.com/repos/ferquintero2013/TestUtel/contents/ferney"
response = requests.get(url)

# Ver que status devolvio (200 = OK, 404 = no encontrado, etc.)
print("Status code", response.status_code)

#Ver el contenido en JSON
data = response.json()
print("Cantidad de items:", len(data))
print("Primer item:", data[0]) 