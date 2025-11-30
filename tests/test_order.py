import os
from datetime import date

import faker

SERVICE_HOST = \
    f"http://{os.environ.get('SERVICE_HOST', '127.0.0.1:8000')}"

fake = faker.Faker()


def test_order_create(api_client):
    response = api_client.post(
        url=f"{SERVICE_HOST}/orders",
        json={
            "order_name": fake.sentence(nb_words=2),
            "start_date": date.today().isoformat(),
        }
    )
    print(response.json())
    assert response.status_code == 200, f"Unexpected status code: {response.status_code}"
    id = response.json().get("id")
    assert id is not None, "Response JSON does not contain 'id'"
    get_response = api_client.get(f"{SERVICE_HOST}/orders/{id}")
    assert get_response.status_code == 200, f"Unexpected status code when getting order: {get_response.status_code}"


def test_order_list_all(api_client):
    response = api_client.get(
        url=f"{SERVICE_HOST}/orders/all"
    )
    print(response.json())
    assert response.status_code == 200, f"Unexpected status code: {response.status_code}"
