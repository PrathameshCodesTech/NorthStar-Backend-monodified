import google.generativeai as genai
import json
from django.conf import settings
from django.db import connections
import re
import logging
from .gemini_config import GEMINI_MODEL_NAME  # ✅ Import auto-detected model

logger = logging.getLogger(__name__)

# Configure Gemini
genai.configure(api_key=settings.GEMINI_API_KEY)

def get_database_schema(database='default'):
    """Get database schema for AI context"""
    try:
        with connections[database].cursor() as cursor:
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """)
            tables = cursor.fetchall()
            
            schema_info = "Database Tables:\n"
            for table in tables:
                table_name = table[0]
                cursor.execute(f"""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = '{table_name}'
                    ORDER BY ordinal_position;
                """)
                columns = cursor.fetchall()
                schema_info += f"\n{table_name}:\n"
                for col in columns:
                    schema_info += f"  - {col[0]} ({col[1]})\n"
            
            return schema_info
    except Exception as e:
        return f"Error getting schema: {str(e)}"

def validate_sql(sql):
    """Validate SQL for security"""
    sql_upper = sql.upper().strip()
    
    # Must be SELECT only
    if not sql_upper.startswith('SELECT'):
        return False, "Only SELECT queries are allowed"
    
    # Forbidden keywords
    dangerous = ['DELETE', 'DROP', 'TRUNCATE', 'INSERT', 'UPDATE', 'ALTER', 
                 'CREATE', 'EXEC', 'EXECUTE', 'GRANT', 'REVOKE']
    for keyword in dangerous:
        if keyword in sql_upper:
            return False, f"Keyword '{keyword}' is not allowed"
    
    # Block comments (SQL injection prevention)
    if '--' in sql or '/*' in sql or '*/' in sql:
        return False, "Comments are not allowed in queries"
    
    return True, "Valid"

def generate_sql_gemini(question, database='default'):
    """Generate SQL using Gemini with auto-detected model"""
    try:
        schema = get_database_schema(database)
        
        prompt = f"""You are a SQL expert. Generate a PostgreSQL query based on the user's question.

DATABASE SCHEMA:
{schema}

RULES:
1. Generate ONLY a SELECT query
2. DO NOT include database name prefix (no "database_name.table_name")
3. Use only table names directly (e.g., "SELECT * FROM frameworks")
4. Return ONLY the SQL query, no explanations
5. No comments (no -- or /* */)
6. Ensure query is safe and read-only

USER QUESTION: {question}

SQL Query:"""

        # ✅ Use auto-detected model
        logger.info(f"🤖 Using Gemini model: {GEMINI_MODEL_NAME}")
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        response = model.generate_content(prompt)
        
        sql = response.text.strip()
        sql = sql.replace('```sql', '').replace('```', '').strip()
        
        # Remove database prefix if present
        sql = re.sub(r'\b\w+\.([\w]+)', r'\1', sql)
        
        logger.info(f"✅ Generated SQL: {sql}")
        return sql
        
    except Exception as e:
        logger.error(f"❌ Gemini SQL generation error: {str(e)}")
        raise Exception(f"Gemini error: {str(e)}")

def generate_chart_config(question, sql_results, columns):
    """Generate chart configuration using Gemini with auto-detected model"""
    try:
        data_sample = sql_results[:5] if len(sql_results) > 5 else sql_results
        
        prompt = f"""You are a data visualization expert. Based on the user's question and query results, suggest the best chart configuration.

USER QUESTION: {question}

DATA COLUMNS: {', '.join(columns)}

DATA SAMPLE (first 5 rows):
{json.dumps(data_sample, indent=2)}

TOTAL ROWS: {len(sql_results)}

Analyze the data and respond with ONLY a valid JSON object (no markdown, no explanations) with this structure:
{{
  "chartType": "bar|line|pie|scatter|table|metric",
  "title": "Chart title",
  "description": "Brief insight about the data",
  "xAxis": "column_name_for_x_axis",
  "yAxis": "column_name_for_y_axis",
  "labelColumn": "column_for_labels (for pie/bar)",
  "valueColumn": "column_for_values",
  "insights": ["insight 1", "insight 2", "insight 3"],
  "recommendation": "What this data shows"
}}

CHART TYPE SELECTION GUIDE:
- "metric": For single numeric values (counts, totals)
- "pie": For categorical data with values (max 10 categories)
- "bar": For comparing categories or time series
- "line": For trends over time
- "table": For detailed data with many columns
- "scatter": For showing relationships between two numeric variables

IMPORTANT: Return ONLY valid JSON, no markdown formatting."""

        # ✅ Use auto-detected model
        logger.info(f"🤖 Using Gemini model for chart config: {GEMINI_MODEL_NAME}")
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        response = model.generate_content(prompt)
        
        config_text = response.text.strip()
        config_text = config_text.replace('```json', '').replace('```', '').strip()
        
        config = json.loads(config_text)
        
        # Ensure required fields exist
        required_fields = ['chartType', 'title']
        for field in required_fields:
            if field not in config:
                config[field] = 'table' if field == 'chartType' else 'Data Visualization'
        
        logger.info(f"✅ Generated chart config: {config['chartType']} - {config['title']}")
        return config
        
    except json.JSONDecodeError as e:
        logger.warning(f"⚠️  JSON decode error, falling back to table view: {str(e)}")
        return {
            "chartType": "table",
            "title": "Query Results",
            "description": "Displaying data in table format",
            "insights": ["Data retrieved successfully"],
            "recommendation": "Review the data in table format"
        }
    except Exception as e:
        logger.error(f"❌ Chart config generation error: {str(e)}")
        raise Exception(f"Chart config generation error: {str(e)}")

def execute_query(sql, database='default'):
    """Execute SQL query and return results"""
    try:
        with connections[database].cursor() as cursor:
            cursor.execute(sql)
            columns = [col[0] for col in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            logger.info(f"✅ Query executed successfully: {len(results)} rows returned")
            return results, columns
            
    except Exception as e:
        logger.error(f"❌ Query execution error: {str(e)}")
        raise Exception(f"Query execution error: {str(e)}")