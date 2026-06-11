@app.route("/download", methods=["GET"])
@rate_limit
async def download():
    """
    Stream file through backend proxy.
    Supports:
    - Large files
    - Range Requests
    - Video seeking
    - Download resume
    """

    try:
        url = request.args.get("url")
        pwd = request.args.get("pwd", "")
        index = int(request.args.get("index", "0"))

        if not url:
            return jsonify({
                "status": "error",
                "message": "Missing url parameter"
            }), 400

        files = await fetch_download_link(url, pwd)

        if isinstance(files, dict):
            return jsonify(files), 500

        if not files:
            return jsonify({
                "status": "error",
                "message": "No files found"
            }), 404

        if index >= len(files):
            return jsonify({
                "status": "error",
                "message": "Invalid file index"
            }), 400

        file_item = files[index]

        dlink = file_item.get("dlink")

        if not dlink:
            return jsonify({
                "status": "error",
                "message": "No download link available"
            }), 404

        cookies = load_cookies()

        proxy_headers = headers.copy()

        range_header = request.headers.get("Range")

        if range_header:
            proxy_headers["Range"] = range_header

        timeout = aiohttp.ClientTimeout(
            total=None,
            connect=30,
            sock_connect=30,
            sock_read=None
        )

        session = aiohttp.ClientSession(
            cookies=cookies,
            headers=proxy_headers,
            timeout=timeout
        )

        upstream = await session.get(
            dlink,
            allow_redirects=True
        )

        async def generate():
            try:
                async for chunk in upstream.content.iter_chunked(
                    1024 * 1024
                ):
                    yield chunk
            finally:
                await upstream.release()
                await session.close()

        response = Response(
            generate(),
            status=upstream.status,
            content_type=upstream.headers.get(
                "Content-Type",
                "application/octet-stream"
            ),
            direct_passthrough=True
        )

        pass_headers = [
            "Content-Length",
            "Content-Range",
            "Content-Disposition",
            "ETag",
            "Last-Modified"
        ]

        for header in pass_headers:
            if header in upstream.headers:
                response.headers[header] = upstream.headers[header]

        response.headers["Accept-Ranges"] = "bytes"
        response.headers["Access-Control-Allow-Origin"] = "*"

        return response

    except Exception as e:
        logging.error(
            f"Download proxy error: {e}",
            exc_info=True
        )

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
