from lapps.discriminators import Uri

# (parital) list of spacy ner entity types
# "category": "CARDINAL"
# "category": "DATE"
# "category": "GPE"
# "category": "LOC"
# "category": "MONEY"
# "category": "ORDINAL"
# "category": "PERSON"
# "category": "QUANTITY"
# "category": "TIME"
# "category": "ORG"
# "category": "PERCENT"
# "category": "WORK_OF_ART"
# "category": "PRODUCT"
# "category": "LANGUAGE"
# "category": "EVENT"
# "category": "NORP"
# "category": "FAC"

config = {Uri.NE:
    {"entity_types": [{
        "type": "PERSON",
        "labels": ["Person", "Per", "PERSON"],
        "bgColor": "#f1cc22",
        "borderColor": "darken"
    }, {
        "type": "TIME",
        "labels": ["Time", "DATE", "TIME"],
        "bgColor": "#ff33aa",
        "borderColor": "darken"
    }, {
        "type": "NUMBER",
        "labels": ["Number", "Num", "CARDINAL", "ORDINAL", "MONEY", "QUANTITY"],
        "bgColor": "#f12c7a",
        "borderColor": "darken"
    }, {
        "type": "WORK",
        "labels": ["WORK_OF_ART", "PRODUCT", "LANGUAGE"],
        "bgColor": "#f1ff47",
        "borderColor": "darken"
    }, {
        "type": "MICS",
        "labels": ["EVENT", "NORP", "FAC"],
        "bgColor": "#11f447",
        "borderColor": "darken"
    }, {
        "type": "LOCATION",
        "labels": ["Location", "Loc", "LOC", "GPE"],
        "bgColor": "#f1f447",
        "borderColor": "darken"
    }, {
        "type": "ORGANIZATION",
        "labels": ["Organization", "Org", "ORG"],
        "bgColor": "#8fb2ff",
        "borderColor": "darken"
    }],
        "relation_types": []
    }
}

