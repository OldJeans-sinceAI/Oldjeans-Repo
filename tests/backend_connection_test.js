require('dotenv').config();
const axios = require('axios');

async function testYextConnection() {
  const baseUrl = process.env.YEXT_BASE_URL || 'https://sbx-api.yextapis.com/';
  const apiKey = process.env.YEXT_API_KEY;
  const entityId = process.env.YEXT_ENTITY_ID;
  const v = process.env.YEXT_API_VERSION || '20261106';

  // Construct endpoint following Yext's sandbox specifications (using 'me' for account ID)
  const url = `${baseUrl}v2/accounts/me/entities/${entityId}`;

  try {
    console.log(`Testing connection to Yext Sandbox for entity: ${entityId}...`);
    const response = await axios.get(url, {
      params: {
        api_key: apiKey,
        v: v
      }
    });

    console.log('✅ Success! Backend connected to Yext Sandbox.');
    console.log('Business Name:', response.data.response.name);
  } catch (error) {
    console.error('❌ Connection failed:');
    if (error.response && error.response.data) {
      console.error(JSON.stringify(error.response.data, null, 2));
    } else {
       console.error(error.message);
    }
    process.exitCode = 1;
  }
}

testYextConnection();