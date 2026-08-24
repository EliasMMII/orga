import requests


WCA_LIVE_GRAPHQL_URL = (
    "https://live.worldcubeassociation.org/api/graphql"
)


def format_wca_time(value):

    if value is None:
        return "N/A"

    if isinstance(value, int):

        if value == -1:
            return "DNF"

        if value == -2:
            return "DNS"

        if value <= 0:
            return "N/A"

        cs = value % 100
        seconds = (value // 100) % 60
        minutes = (value // 100) // 60

        if minutes > 0:
            return f"{minutes}:{seconds:02d}.{cs:02d}"

        return f"{seconds}.{cs:02d}"

    return str(value)


def graphql_request(
    query,
    variables=None
):

    try:

        response = requests.post(
            WCA_LIVE_GRAPHQL_URL,
            json={
                "query": query,
                "variables": variables or {}
            },
            headers={
                "Content-Type":
                    "application/json",
                "Accept":
                    "application/json"
            },
            timeout=20
        )

    except requests.exceptions.RequestException as e:

        print(
            "Fehler beim Verbinden mit "
            "WCA Live:"
        )

        print(e)

        return None

    print(
        f"HTTP Status: "
        f"{response.status_code}"
    )

    try:

        data = response.json()

    except ValueError:

        print(
            "WCA Live hat kein JSON "
            "zurückgegeben."
        )

        print(
            response.text[:1000]
        )

        return None

    if "errors" in data:

        print()
        print(
            "GraphQL-Fehler:"
        )

        for error in data["errors"]:

            print(
                error.get(
                    "message",
                    error
                )
            )

        return None

    return data.get(
        "data"
    )


def test_wca_live():

    print()
    print("=" * 60)
    print("TESTE WCA LIVE GRAPHQL")
    print("=" * 60)
    print()

    query = """
    query {
        __schema {
            queryType {
                name
            }
        }
    }
    """

    data = graphql_request(
        query
    )

    if not data:

        print()
        print(
            "Keine GraphQL-Daten erhalten."
        )

        return False

    print(
        "GraphQL-Verbindung funktioniert."
    )

    print(
        "Query-Typ:",
        data["__schema"]["queryType"]["name"]
    )

    return True


def get_competition_podiums(
    competition_id
):

    print()
    print("=" * 60)
    print("WCA LIVE")
    print("=" * 60)

    print(
        f"Competition: {competition_id}"
    )

    # --------------------------------------------------
    # Zuerst testen wir nur die Verbindung.
    # --------------------------------------------------

    if not test_wca_live():

        return None

    print()
    print(
        "WCA Live ist erreichbar."
    )

    print()
    print(
        "Als nächstes muss die konkrete "
        "Competition-Query verwendet werden."
    )

    print(
        "Competition-ID:",
        competition_id
    )

    return None