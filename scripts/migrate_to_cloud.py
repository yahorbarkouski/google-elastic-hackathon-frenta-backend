import asyncio
import sys
from elasticsearch import AsyncElasticsearch


async def migrate_elasticsearch(source_url: str, target_url: str, api_key: str):
    source_client = AsyncElasticsearch(source_url)
    target_client = AsyncElasticsearch(
        target_url,
        api_key=api_key
    )
    
    indices = ["apartments", "rooms", "neighborhoods"]
    
    try:
        for index_name in indices:
            print(f"\n=== Migrating {index_name} ===")
            
            exists = await source_client.indices.exists(index=index_name)
            if not exists:
                print(f"Index {index_name} does not exist in source, skipping")
                continue
            
            mapping = await source_client.indices.get_mapping(index=index_name)
            settings = await source_client.indices.get_settings(index=index_name)
            
            target_exists = await target_client.indices.exists(index=index_name)
            if target_exists:
                print(f"Deleting existing {index_name} in target")
                await target_client.indices.delete(index=index_name)
            
            print(f"Creating {index_name} in target")
            await target_client.indices.create(
                index=index_name,
                body={
                    "mappings": mapping[index_name]["mappings"],
                    "settings": {
                        "number_of_shards": settings[index_name]["settings"]["index"].get("number_of_shards", "1"),
                        "number_of_replicas": "1"
                    }
                }
            )
            
            count_response = await source_client.count(index=index_name)
            total_docs = count_response["count"]
            print(f"Found {total_docs} documents to migrate")
            
            if total_docs == 0:
                continue
            
            docs_response = await source_client.search(
                index=index_name,
                body={"query": {"match_all": {}}, "size": 10000}
            )
            
            docs = docs_response["hits"]["hits"]
            print(f"Fetched {len(docs)} documents")
            
            bulk_body = []
            for doc in docs:
                bulk_body.append({"index": {"_index": index_name, "_id": doc["_id"]}})
                bulk_body.append(doc["_source"])
            
            if bulk_body:
                print(f"Bulk indexing {len(docs)} documents")
                await target_client.bulk(operations=bulk_body)
            
            await target_client.indices.refresh(index=index_name)
            
            target_count = await target_client.count(index=index_name)
            print(f"✓ Migrated {target_count['count']}/{total_docs} documents")
        
        print("\n✓ Migration complete!")
        
    finally:
        await source_client.close()
        await target_client.close()


async def main():
    if len(sys.argv) != 3:
        print("Usage: python migrate_to_cloud.py <target_url> <api_key>")
        print("Example: python migrate_to_cloud.py https://xxx.es.cloud.es.io:443 your_api_key")
        sys.exit(1)
    
    source_url = "http://localhost:9200"
    target_url = sys.argv[1]
    api_key = sys.argv[2]
    
    print(f"Migrating from {source_url} to {target_url}")
    print("This will DELETE and recreate all indices in the target\n")
    
    confirm = input("Continue? (yes/no): ")
    if confirm.lower() != "yes":
        print("Aborted")
        sys.exit(0)
    
    await migrate_elasticsearch(source_url, target_url, api_key)


if __name__ == "__main__":
    asyncio.run(main())

