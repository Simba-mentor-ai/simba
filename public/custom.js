window.addEventListener("chainlit-call-fn", (e) => {
  const { name, args, callback } = e.detail;
  if (name === "url_query_parameter") {
    callback((new URLSearchParams(window.location.search)).get(args.msg));
  }
});