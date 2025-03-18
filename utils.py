import base64

def generate_uri(entity_data, base_uri = "http://wistor.nl/entities/"):
    """Generate a deterministic URI for a WKT entity"""
    # Create a unique identifier based on entity properties
    entity_type = entity_data['type']
    layer = entity_data['layer']
    
    # Use relevant parts of the WKT and extra data for URI generation, This ensures similar entities get similar URIs
    key_parts = [
        entity_type,
        layer,
        str(entity_data['color'])
    ]
    
    # Add relevant extra data based on entity type
    if 'center' in entity_data['extra_data']:
        key_parts.append(entity_data['extra_data']['center'])
    elif 'location' in entity_data['extra_data']:
        key_parts.append(entity_data['extra_data']['location'])
    elif 'start_point' in entity_data['extra_data']:
        key_parts.append(entity_data['extra_data']['start_point'])
    
    # Join key parts with a delimiter that won't appear in your data
    joined_parts = "||".join(key_parts)
    
    # Base64 encode for URL safety
    identifier = base64.urlsafe_b64encode(joined_parts.encode()).decode()
    
    # Format URI
    clean_layer = layer.replace(' ', '_').lower()
    clean_type = entity_type.lower()
    
    return f"{base_uri}{clean_layer}/{clean_type}/{identifier}"

def decode_uri(uri):
    # Extract the identifier part
    identifier = uri.split('/')[-1]
    
    # Decode the base64 data
    decoded = base64.urlsafe_b64decode(identifier).decode()
    
    # Split back into key parts
    key_parts = decoded.split('||')
    
    return key_parts