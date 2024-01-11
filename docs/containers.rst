##########
Containers
##########

There are two implementation options.

1. On a local host, i.e., a PC.

2. On a cloud computer as a serverless lambda.

Local Host
==========

On a local host, i.e, a PC, the configuration looks like this:

..  plantuml::

    @startuml

    node local {
        component python
        component feederreader
        python --> feederreader
        database history
        folder "web pages" as html
        component browser
    }
    node AOUSC {
        file RSS
    }
    () email

    feederreader --> RSS
    feederreader <--> history
    feederreader --> email
    feederreader --> html

    actor Journalist

    Journalist <-- email
    browser --> html
    Journalist --> browser

    @enduml

This requires either manually running the application periodically,
or leaving it running in a terminal window.

Cloud
=====

When using a cloud implementation, the configuration looks like this:


..  plantuml::

    @startuml
    !include <aws/common>
    !include <aws/Storage/AmazonS3/AmazonS3>
    !include <aws/Compute/AWSLambda/AWSLambda>
    !include <aws/Messaging/AmazonSES/AmazonSES>

    actor Journalist

    node PC {
        component browser
    }

    node AOUSC {
        file RSS
    }

    cloud AWS {
        node lambda <<$AWSLambda>> {
            component feederreader
        }

        database S3  <<$AmazonS3>> {
            database history
            folder "web pages" as html
        }


        rectangle SES <<$AmazonSES>> {
            () email
        }
    }

    feederreader --> RSS
    feederreader <--> history
    feederreader ---> email
    feederreader --> html

    Journalist <-- email
    browser --> html
    Journalist -- browser

    @enduml

This runs independently.

AWS cloud infrastructure requires a Cloud Formation Template to build the resources:

-   The S3 bucket.

-   The Lambda.

Also, the email domain information must be verified with Amazon to permit sending email.
This means setting up an "me.admin@gmail.com" address in addition to "me@gmail.com".
A verification email must be sent and confirmed by AWS.

Further, the lambda must be configured with the ARN (Amazon Resource Name) for the S3 bucket.


Summary
=======

Note that the components are the same.
The host processing each component is distinct.
