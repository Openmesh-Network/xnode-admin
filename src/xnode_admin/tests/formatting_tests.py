from nix_rebuilder import parse_nix_json
import json

with open("mock_studio_message.json", "r") as f:
    mock_data =  f.read()
mock_json = json.loads(mock_data)
print("______________XXXXXX_______________\n", mock_json["services"], "\n______________XXXXXX_______________")

def test():
    final_format = "{"
    for module_type in mock_json:
        print(module_type + "SERVICES SERVICES SERVICES SERVICES SERVICES ")
        final_format += module_type + " = {\n"
        final_format += parse_nix_json(mock_json[module_type], "")
        final_format += "};\n"

    final_format += "}"    
    print("----------------- FINAL FORM -----------------")
    print(final_format)
test()

my_test_json = {
    "services": [{
        "nixName": "minecraft-server",
        "options": [
            {
                "nixName": "eula",
                "type": "boolean",
                "value": "true"
            },
            {
                "nixName": "declarative",
                "type": "boolean",
                "value": "true"
            }
        ]
    },
    {
        "nixName": "minecraft-server2",
        "options": [
            {
                "nixName": "eula",
                "type": "boolean",
                "value": "true"
            },
            {
                "nixName": "declarative",
                "type": "boolean",
                "value": "true"
            }
        ]
    },
    {
        "nixName": "minecraft-server3",
        "options": [
            {
                "nixName": "eula",
                "type": "boolean",
                "value": "true"
            },
            {
                "nixName": "declarative",
                "type": "boolean",
                "value": "true"
            },
            {
                "nixName": "serverProperties",
                "options":[
                    {
                        "nixName": "maxPlayers",
                        "type": "int",
                        "value": "555"
                    }
                ]
            }
        ]
    },
    ]
}
print(parse_nix_json(my_test_json["services"]))
#print(parse_nix_json(mock_json["services"]))
