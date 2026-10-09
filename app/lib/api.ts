export async function readApiJson<T = Record<string, any>>(response: Response): Promise<T> {
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.toLowerCase().includes('application/json')) {
    const reason = response.status === 404
      ? 'The API route was not found.'
      : 'The server returned a web page instead of API data.';
    throw new Error(`${reason} Check that FastAPI is running on port 8000 and restart the frontend.`);
  }
  try {
    return await response.json() as T;
  } catch {
    throw new Error('The API response was not valid JSON. Check the backend log and try again.');
  }
}
