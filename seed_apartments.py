import asyncio
import httpx

BASE_URL = "http://localhost:8000"

async def seed_apartments():
    async with httpx.AsyncClient(timeout=600.0) as client:
        print("Step 1: Seeding real Airbnb apartments...")
        
        apartments = [
            {
                "apartment_id": "apt_brooklyn_victorian",
                "address": "Brooklyn, New York, United States",
                "neighborhood_id": "brooklyn_prospect_park",
                "rent_price": 850.0,
                "availability_dates": [
                    {"start": "2025-11-15", "end": "2026-03-31"}
                ],
                "document": """Room in Brooklyn, New York, United States
Shared bathroom, 1 single bed. 
COZY VICTORIAN TOWNHOUSE IN SAFE HISTORIC LANDMARK DISTRICT CLOSE TO PUBLIC TRANSPORTATION, 30-40 MINUTES TO TIMES SQUARE. CLOSE TO PROSPECT PARK, BROOKLYN BOTANICAL GARDENS, LIBRARIES, MUSEUM, RESTAURANTS, SUPER MARKETS, DELIS.
NO SMOKING.
PUBLIC SECURITY CAMERAS.

The room is located on the third floor of a walk up.

Entire house has Aquasana Rhino water Filtration system.

Security cameras located on front of house covering front yard, front door entrance and stairways.

The space:
A truly beautiful, comfortable small room with a twin size bed, lots of shelving space, a desk and chair, ceiling and desk fan. It is located on the third floor of an authentic walk up Victorian Town House. It has a window facing the street with a view of the front garden which is very beautiful during the summer and early autumn. Many guests have verbalized that the space gives an extremely warm, cozy, feeling of being at home. A very popular space.

Again, to reiterate - this is a small room. With a twin size bed. Only suitable for one person.

Guest access:
WIFI, refrigerator, microwave, electric kettle and a two ring electric burner. Perfect for preparing light meals.

During your stay:
Moderate to minimal - great setting for busy energetic international students, creative people who want to explore the city, for people attending seminars or who are working on special assignments etc.

Other things to note:
Minimum 5 nights.

Conveniently located close to transportation. Supermarkets, delis and restaurants are close by. Laundromat at top of the street.

Very racially, culturally and socioeconomically diverse vicinity.

Safe location.

Generally very quiet but can get loud at times with city sounds.

Please no food items or eating in room. There's a kitchen for that.

This room is not air conditioned. There are fans.""",
                "image_urls": [
                    "https://a0.muscache.com/im/pictures/airflow/Hosting-6146783/original/c52a66aa-02d6-4c93-9d37-71b46efafb2c.jpg?im_w=720",
                    "https://a0.muscache.com/im/pictures/a35906a9-7ea7-430c-9a12-baa30b3a2b90.jpg?im_w=720",
                    "https://a0.muscache.com/im/pictures/airflow/Hosting-6146783/original/f306e540-1737-47cf-80c2-931f44edeff3.jpg?im_w=720",
                    "https://a0.muscache.com/im/pictures/airflow/Hosting-6146783/original/1c78fc6e-0a48-4207-a02d-11fe076d872b.jpg?im_w=720"
                ]
            },
            {
                "apartment_id": "apt_manhattan_hudson_yards",
                "address": "Hudson Yards, Manhattan, New York, United States",
                "neighborhood_id": "hudson_yards",
                "rent_price": 3200.0,
                "availability_dates": [
                    {"start": "2025-12-01", "end": "2026-02-28"}
                ],
                "document": """Flat with an amazing view!

Entire rental unit in New York, United States

Located smack dab in the center of Manhattan you can get anywhere in the city within minutes. Located in the popular New Hudson Yards development area this stylish, new apartment gives you peace and tranquility while at home but steps from the hustle and bustle of the city when you step outside. 

Apartment features full kitchen, washer dryer, king sized bedroom and gym within the building.

Registration Details: Exempt""",
                "image_urls": [
                    "https://a0.muscache.com/im/pictures/hosting/Hosting-968117958661367161/original/175771f3-6d6e-4e94-9e48-3d007868d661.jpeg?im_w=720",
                    "https://a0.muscache.com/im/pictures/miso/Hosting-968117958661367161/original/26de860a-b970-46a1-8c61-e6e36eed07b1.jpeg?im_w=720",
                    "https://a0.muscache.com/im/pictures/miso/Hosting-968117958661367161/original/e034be1c-d3b0-4796-8425-3cc0cdde05b1.jpeg?im_w=720",
                    "https://a0.muscache.com/im/pictures/miso/Hosting-968117958661367161/original/a2d4fc30-91b2-44fc-9133-a76fc4457b53.jpeg?im_w=720"
                ]
            }
        ]
        
        print("\nStep 2: Indexing apartments...")
        for i, apt in enumerate(apartments, 1):
            print(f"\n📍 Indexing apartment {i}/2: {apt['apartment_id']}")
            print(f"   Address: {apt['address']}")
            print(f"   Photos: {len(apt['image_urls'])} images")
            print(f"   Document length: {len(apt['document'])} characters")
            
            try:
                response = await client.post(
                    f"{BASE_URL}/api/index",
                    json=apt
                )
                
                print(f"   Response status: {response.status_code}")
                
                result = response.json()
                
                if response.status_code == 200:
                    print(f"   ✅ Successfully indexed!")
                    print(f"   Total features: {result.get('total_features', 0)}")
                    print(f"   Domain breakdown: {result.get('domain_breakdown', {})}")
                else:
                    print(f"   ❌ Error response: {result}")
            except Exception as e:
                import traceback
                print(f"   ❌ Error indexing: {e}")
                print(f"   Traceback: {traceback.format_exc()}")
        
        print("\n" + "="*60)
        print("✅ Seeding complete!")
        print("="*60)
        
        print("\n🔍 Try searching for:")
        print("  - 'small room near Prospect Park'")
        print("  - 'apartment with washer dryer in Manhattan'")
        print("  - 'Victorian townhouse in Brooklyn'")
        print("  - 'place with gym and kitchen'")
        print("  - 'shared room close to public transportation'")

if __name__ == "__main__":
    asyncio.run(seed_apartments())
