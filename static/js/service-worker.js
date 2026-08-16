/* ============================================================
   WORKLOAD SERVICE WORKER
   ============================================================ */

const CACHE_NAME = "workload-v1";


/* ============================================================
   INSTALL
   ============================================================ */

self.addEventListener("install", function(event) {

    console.log("Workload service worker installed.");

    self.skipWaiting();

});


/* ============================================================
   ACTIVATE
   ============================================================ */

self.addEventListener("activate", function(event) {

    console.log("Workload service worker activated.");

    event.waitUntil(
        self.clients.claim()
    );

});


/* ============================================================
   PUSH NOTIFICATION
   ============================================================ */

self.addEventListener("push", function(event) {

    console.log("Push notification received.");

    let data = {};

    try {

        if (event.data) {

            data = event.data.json();

        }

    }

    catch (error) {

        console.error(
            "Unable to parse push notification:",
            error
        );

        data = {

            title: "Workload",

            message:
                event.data
                    ? event.data.text()
                    : "You have a new notification."

        };

    }


    const title =
        data.title ||
        "Workload";


    const message =
        data.message ||
        data.body ||
        "You have a new notification.";


    const notificationUrl =
        data.url ||
        "/";


    const options = {

        body: message,

        icon:
            "/static/images/icon-192.png",

        badge:
            "/static/images/icon-192.png",

        data: {

            url:
                notificationUrl

        },

        requireInteraction:
            false,

        vibrate: [
            200,
            100,
            200
        ]

    };


    event.waitUntil(

        self.registration.showNotification(
            title,
            options
        )

    );

});


/* ============================================================
   NOTIFICATION CLICK
   ============================================================ */

self.addEventListener(
    "notificationclick",
    function(event) {

        console.log(
            "Workload notification clicked."
        );


        event.notification.close();


        const url =
            event.notification &&
            event.notification.data &&
            event.notification.data.url
                ? event.notification.data.url
                : "/";


        event.waitUntil(

            clients.matchAll({

                type: "window",

                includeUncontrolled: true

            })

            .then(function(clientList) {

                /*
                 * If Workload is already open,
                 * focus the existing window.
                 */

                for (
                    const client of clientList
                ) {

                    if (
                        client.url.includes(
                            window.location.origin
                        ) &&
                        "focus" in client
                    ) {

                        return client
                            .navigate(url)
                            .then(function() {

                                return client.focus();

                            });

                    }

                }


                /*
                 * Otherwise open a new window.
                 */

                if (
                    clients.openWindow
                ) {

                    return clients.openWindow(
                        url
                    );

                }

            })

        );

    }
);


/* ============================================================
   NOTIFICATION CLOSE
   ============================================================ */

self.addEventListener(
    "notificationclose",
    function(event) {

        console.log(
            "Workload notification closed."
        );

    }
);


/* ============================================================
   FETCH
   ============================================================ */

self.addEventListener(
    "fetch",
    function(event) {

        /*
         * We are not caching Django pages.
         * This allows the application to always
         * request fresh notification data.
         */

        return;

    }
);