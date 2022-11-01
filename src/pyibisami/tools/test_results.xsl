<?xml version="1.0" encoding="ISO-8859-1"?>

<xsl:stylesheet version="1.0"
xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

<xsl:template match="/">
    <html>
        <body>
            <h2><a name="summary">Test Results - Summary</a></h2>
            <table border="1">
                <tr bgcolor="#9acd32">
                    <th>Test Name</th>
                    <th>Result</th>
                    <th>Description</th>
                </tr>
              <xsl:for-each select="tests/test">
                <tr>
                    <td><a href="#{name}"><xsl:value-of select="name"/></a></td>
                    <td><xsl:value-of select="result"/></td>
                    <td><xsl:value-of select="description"/></td>
                </tr>
              </xsl:for-each>
            </table>
            <h2>Test Results - Details</h2>
              <xsl:for-each select="tests/test">
                <h3><a name="{name}"><xsl:value-of select="name"/> - <xsl:value-of select="description"/></a></h3>
                    <div style="overflow:auto;height:200px;background-color:lightgray;">
                      <xsl:for-each select="output/block[@type='text']">
                        <h4><xsl:value-of select="./@name"/></h4>
                        <pre><xsl:value-of select="."/></pre>
                      </xsl:for-each>
                    </div>
                  <xsl:for-each select="output/block[@type='image']">
                    <img src="{.}"/>
                  </xsl:for-each>
                    <p><a href="#summary">Back to top.</a></p>
              </xsl:for-each>
        </body>
    </html>
</xsl:template>

</xsl:stylesheet>
