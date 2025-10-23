import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

import httpx

BASE_URL = "http://localhost:8000"

APARTMENTS = [
    {
        "name": "Williamsburg Industrial Loft",
        "description": "Spacious 2-bedroom industrial loft in the heart of Williamsburg, Brooklyn. Soaring 14-foot ceilings with exposed wooden beams and original brick walls. Massive factory windows flooding the space with natural light. Open kitchen with custom white oak cabinets, stainless steel commercial appliances, and concrete countertops. Polished concrete floors throughout. Master bedroom features walk-in closet and exposed ductwork. Modern bathroom with subway tile and rainfall shower. Just two blocks from Bedford Ave L train and surrounded by cafes, galleries, and nightlife.",
        "price_range": {"min": 4000, "max": 4400},
        "num_images": 7,
        "neighborhood_hint": "Williamsburg",
        "city_hint": "NYC"
    },
    {
        "name": "SoHo Luxury Modern",
        "description": "Stunning 1-bedroom luxury apartment in prime SoHo with floor-to-ceiling windows. Contemporary design with white oak herringbone floors, 11-foot ceilings, and pristine white walls. Chef's kitchen with Miele appliances, white marble countertops, and custom Italian cabinetry. Spa-like bathroom with Carrara marble, heated floors, and deep soaking tub. Built-in storage throughout. South-facing windows providing incredible natural light. Building features 24-hour doorman, fitness center, and rooftop terrace. Steps from high-end shopping, art galleries, and Michelin-starred restaurants.",
        "price_range": {"min": 5600, "max": 6000},
        "num_images": 8,
        "neighborhood_hint": "SoHo",
        "city_hint": "NYC"
    },
    {
        "name": "Hudson Yards Modern Studio",
        "description": "Sleek studio apartment in the heart of Hudson Yards with stunning city views. Modern open layout with floor-to-ceiling windows, 10-foot ceilings, and high-end finishes. Compact but efficient kitchen with quartz countertops, stainless steel appliances, and breakfast bar. Contemporary bathroom with glass-enclosed shower and floating vanity. Brazilian cherry hardwood floors, recessed lighting, and smart home features. Full-service building with 24/7 doorman, state-of-the-art fitness center, resident lounge, and package room. Minutes from The Vessel, Hudson River Park, and 7 train.",
        "price_range": {"min": 3100, "max": 3300},
        "num_images": 6,
        "neighborhood_hint": "Hudson Yards",
        "city_hint": "NYC"
    },
    {
        "name": "Upper West Side Classic",
        "description": "Elegant 3-bedroom pre-war apartment on a tree-lined Upper West Side street. Classic New York architecture with 9-foot beamed ceilings, crown molding, and original hardwood floors. Formal entry foyer leads to spacious living and dining rooms. Windowed galley kitchen with white Shaker cabinets, granite counters, and subway tile backsplash. Three generous bedrooms with excellent closet space. Two full bathrooms with vintage tile and clawfoot tubs. Charming pre-war details including decorative fireplace and built-in bookshelves. Near Central Park, excellent schools, Zabar's, and express subway.",
        "price_range": {"min": 6300, "max": 6700},
        "num_images": 8,
        "neighborhood_hint": "Upper West Side",
        "city_hint": "NYC"
    },
    {
        "name": "East Village Bohemian",
        "description": "Charming 1-bedroom walk-up in the vibrant East Village with authentic NYC character. Cozy layout with exposed brick accent wall, original tin ceilings, and wide-plank hardwood floors. Updated kitchen with butcher block counters, open shelving, and vintage-style appliances. Bedroom fits queen bed with bohemian decor and plants. Small but functional bathroom with pedestal sink and subway tile. Large windows with tree-lined street views. Building has bike storage and shared courtyard. Steps from Tompkins Square Park, countless vintage shops, live music venues, and incredible restaurants. Perfect for creative types seeking neighborhood charm.",
        "price_range": {"min": 2700, "max": 2900},
        "num_images": 6,
        "neighborhood_hint": "East Village",
        "city_hint": "NYC"
    },
    {
        "name": "Brooklyn Heights Garden",
        "description": "Rare 2-bedroom garden apartment in historic Brooklyn Heights brownstone with private outdoor space. Sun-drenched corner unit with bay windows, exposed brick, and original hardwood floors. Updated open kitchen with white subway tile, butcher block counters, and stainless appliances. Two bedrooms with excellent natural light and closet space. Renovated bathroom with vintage-style fixtures and hex tile. Private entrance leads to beautiful 400 sq ft garden patio with mature plantings and Brooklyn charm. Quiet tree-lined block near Brooklyn Heights Promenade, Brooklyn Bridge Park, and excellent restaurants. A and C trains nearby.",
        "price_range": {"min": 3500, "max": 3700},
        "num_images": 7,
        "neighborhood_hint": "Brooklyn Heights",
        "city_hint": "NYC"
    },
    {
        "name": "Tribeca Minimalist",
        "description": "Refined 2-bedroom apartment in coveted Tribeca with minimalist contemporary design. Open-concept layout with 10-foot ceilings, oversized windows, and wide-plank white oak floors. Seamless kitchen with custom matte white cabinetry, Caesarstone counters, and premium Bosch appliances. Master suite with walk-in closet and en-suite bathroom featuring marble tile and floating double vanity. Second bedroom ideal for guest room or home office. Modern bathroom with frameless glass shower and wall-hung toilet. In-unit Bosch washer/dryer. Full-service building with live-in super, package room, and common roof deck. Near Hudson River Park and 1/2/3 trains.",
        "price_range": {"min": 5100, "max": 5300},
        "num_images": 8,
        "neighborhood_hint": "Tribeca",
        "city_hint": "NYC"
    },
    {
        "name": "Śródmieście Pre-War",
        "description": "Beautiful 2-bedroom apartment in historic pre-war building in the heart of Śródmieście, Warsaw. High ornate ceilings at 3.5 meters with original decorative moldings and restored herringbone oak parquet floors. Spacious layout with separate living and dining areas. Updated kitchen with modern appliances while maintaining period charm. Two bright bedrooms with tall windows overlooking quiet courtyard. Renovated bathroom with contemporary fixtures and classic tile. Original wooden doors and vintage radiators add character. Building features elegant entrance hall with marble stairs. Walking distance to Old Town, Nowy Świat, theaters, cafes, and excellent public transport connections.",
        "price_range": {"min": 6300, "max": 6700},
        "num_images": 7,
        "neighborhood_hint": "Śródmieście",
        "city_hint": "Warsaw"
    },
    {
        "name": "Praga Modern",
        "description": "Contemporary 1-bedroom apartment in up-and-coming Praga district, Warsaw. Recently renovated with modern Scandinavian-inspired design. Open-plan living area with light gray walls, blonde wood floors, and large windows. Sleek kitchen with white high-gloss cabinets, concrete-look countertops, and integrated appliances. Bedroom fits king bed with built-in wardrobe. Modern bathroom with walk-in shower, geometric tile, and chrome fixtures. Energy-efficient heating and triple-glazed windows. Building with renovated common areas and bike storage. Near Praga Koneser Center, trendy restaurants, vintage shops, and tram lines. Perfect for young professionals seeking modern living in creative neighborhood.",
        "price_range": {"min": 4400, "max": 4600},
        "num_images": 6,
        "neighborhood_hint": "Praga",
        "city_hint": "Warsaw"
    },
    {
        "name": "Mokotów Family",
        "description": "Spacious 3-bedroom family apartment in residential Mokotów, Warsaw. Bright and airy 85m² layout with southwest-facing balcony. Living room with access to balcony perfect for family dining. Functional kitchen with white cabinets, wood countertops, and full-size appliances including dishwasher. Three comfortable bedrooms with ample storage space. Two bathrooms - main with bathtub, second with shower. Oak parquet flooring throughout. Building with elevator, underground parking included, children's playground, and green courtyard. Excellent location near international schools, Morskie Oko metro station, parks, shopping centers, and family-friendly amenities.",
        "price_range": {"min": 7600, "max": 8000},
        "num_images": 8,
        "neighborhood_hint": "Mokotów",
        "city_hint": "Warsaw"
    }
]


async def generate_apartment_batch():
    timeout_config = httpx.Timeout(
        connect=10.0,
        read=180.0,
        write=10.0,
        pool=10.0
    )
    
    results = []
    errors = []
    
    print("=" * 80)
    print("BATCH APARTMENT GENERATION")
    print("=" * 80)
    print(f"Starting generation of {len(APARTMENTS)} diverse apartments")
    print(f"Target: 7 New York + 3 Warsaw")
    print(f"Start time: {datetime.now().isoformat()}\n")
    
    async with httpx.AsyncClient(timeout=timeout_config, base_url=BASE_URL) as client:
        for idx, apt_config in enumerate(APARTMENTS, 1):
            city_name = apt_config.get("city_hint", "NYC")
            print(f"\n{'='*80}")
            print(f"[{idx}/{len(APARTMENTS)}] Generating: {apt_config['name']}")
            print(f"{'='*80}")
            print(f"City: {city_name}")
            print(f"Neighborhood: {apt_config['neighborhood_hint']}")
            print(f"Price range: ${apt_config['price_range']['min']}-${apt_config['price_range']['max']}")
            print(f"Images: {apt_config['num_images']}")
            print(f"Description: {apt_config['description'][:100]}...")
            
            try:
                print(f"\n[Step 1/{idx}] Generating preview with images...")
                preview_response = await client.post(
                    "/api/apartments/generate/preview",
                    json={
                        "description": apt_config["description"],
                        "price_range": apt_config["price_range"],
                        "num_images": apt_config["num_images"],
                        "neighborhood_hint": apt_config["neighborhood_hint"],
                        "city_hint": apt_config["city_hint"],
                        "aspect_ratio": "16:9"
                    }
                )
                
                if preview_response.status_code != 200:
                    error_msg = f"Preview generation failed: {preview_response.text}"
                    print(f"❌ {error_msg}")
                    errors.append({
                        "apartment": apt_config["name"],
                        "step": "preview",
                        "error": error_msg
                    })
                    continue
                
                preview = preview_response.json()
                preview_id = preview["preview_id"]
                apartment_id = preview["apartment_id"]
                
                print(f"✓ Preview generated")
                print(f"  Preview ID: {preview_id}")
                print(f"  Apartment ID: {apartment_id}")
                print(f"  Title: {preview['title']}")
                print(f"  Address: {preview['address']}")
                print(f"  Price: ${preview['rent_price']}/month")
                print(f"  Images: {preview['num_images']}")
                
                print(f"\n[Step 2/{idx}] Confirming and indexing...")
                confirm_response = await client.post(
                    "/api/apartments/generate/confirm",
                    json={"preview_id": preview_id}
                )
                
                if confirm_response.status_code != 200:
                    error_msg = f"Confirmation failed: {confirm_response.text}"
                    print(f"❌ {error_msg}")
                    errors.append({
                        "apartment": apt_config["name"],
                        "step": "confirm",
                        "error": error_msg,
                        "preview_id": preview_id
                    })
                    continue
                
                result = confirm_response.json()
                print(f"✓ Apartment indexed successfully")
                print(f"  Elasticsearch ID: {result['elasticsearch_id']}")
                
                results.append({
                    "config_name": apt_config["name"],
                    "apartment_id": apartment_id,
                    "title": preview["title"],
                    "address": preview["address"],
                    "city": city_name,
                    "neighborhood": apt_config["neighborhood_hint"],
                    "rent_price": preview["rent_price"],
                    "num_images": preview["num_images"],
                    "elasticsearch_id": result["elasticsearch_id"]
                })
                
                print(f"✅ Apartment {idx}/{len(APARTMENTS)} complete: {preview['title']}")
                
            except Exception as e:
                import traceback
                error_msg = f"Unexpected error: {str(e)}"
                print(f"❌ {error_msg}")
                print(f"Traceback: {traceback.format_exc()}")
                errors.append({
                    "apartment": apt_config["name"],
                    "step": "exception",
                    "error": error_msg
                })
    
    print(f"\n{'='*80}")
    print("BATCH GENERATION COMPLETE")
    print(f"{'='*80}")
    print(f"End time: {datetime.now().isoformat()}")
    print(f"Total successful: {len(results)}/{len(APARTMENTS)}")
    print(f"Total errors: {len(errors)}")
    
    if results:
        print(f"\n✅ SUCCESSFULLY GENERATED APARTMENTS:")
        print(f"{'='*80}")
        
        nyc_count = sum(1 for r in results if r["city"] == "NYC")
        warsaw_count = sum(1 for r in results if r["city"] == "Warsaw")
        
        print(f"\nNew York: {nyc_count}")
        for r in results:
            if r["city"] == "NYC":
                print(f"  - {r['title']} ({r['neighborhood']}) - ${r['rent_price']}/mo - {r['num_images']} images")
        
        print(f"\nWarsaw: {warsaw_count}")
        for r in results:
            if r["city"] == "Warsaw":
                print(f"  - {r['title']} ({r['neighborhood']}) - ${r['rent_price']}/mo - {r['num_images']} images")
    
    if errors:
        print(f"\n❌ ERRORS:")
        print(f"{'='*80}")
        for err in errors:
            print(f"  - {err['apartment']}: {err['error']}")
    
    report = {
        "generated_at": datetime.now().isoformat(),
        "total_attempted": len(APARTMENTS),
        "total_successful": len(results),
        "total_failed": len(errors),
        "success_rate": f"{(len(results)/len(APARTMENTS)*100):.1f}%",
        "results": results,
        "errors": errors
    }
    
    report_path = Path("./output/batch_generation_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2))
    
    print(f"\n📄 Report saved: {report_path}")
    
    return report


async def main():
    try:
        report = await generate_apartment_batch()
        
        if report["total_failed"] > 0:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Generation interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

